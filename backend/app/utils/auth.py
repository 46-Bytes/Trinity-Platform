"""
Authentication and authorization utilities.
"""
import logging
import requests as http_requests
from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime, timezone
from uuid import UUID
from ..database import get_db
from ..models.user import User, UserRole
from ..models.impersonation import ImpersonationSession
from ..config import settings
from typing import Optional, List

logger = logging.getLogger(__name__)

# Cached JWKS data for Auth0 token verification
_jwks_cache: Optional[dict] = None


def _get_auth0_jwks() -> dict:
    """Fetch and cache Auth0 JWKS (JSON Web Key Set) for RS256 verification."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    jwks_url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
    response = http_requests.get(jwks_url, timeout=10)
    response.raise_for_status()
    _jwks_cache = response.json()
    return _jwks_cache


def _get_auth0_signing_key(token: str) -> dict:
    """Get the correct signing key from Auth0 JWKS for the given token."""
    jwks = _get_auth0_jwks()
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if not kid:
        raise JWTError("Token header missing 'kid'")
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            return key
    # Key not found — JWKS may have rotated, clear cache and retry once
    global _jwks_cache
    _jwks_cache = None
    jwks = _get_auth0_jwks()
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            return key
    raise JWTError(f"Unable to find signing key with kid: {kid}")


def decode_auth0_token(token: str) -> dict:
    """
    Verify and decode an Auth0 RS256 JWT against the Auth0 JWKS endpoint.
    Raises JWTError if verification fails.
    """
    signing_key = _get_auth0_signing_key(token)
    payload = jwt.decode(
        token,
        signing_key,
        algorithms=[settings.AUTH0_ALGORITHMS],
        options={"verify_aud": False},
        issuer=f"https://{settings.AUTH0_DOMAIN}/",
    )
    # Manually validate audience (python-jose only accepts a single string)
    token_aud = payload.get("aud")
    valid_audiences = {settings.AUTH0_AUDIENCE, settings.AUTH0_CLIENT_ID}
    if isinstance(token_aud, list):
        if not valid_audiences.intersection(token_aud):
            raise JWTError("Invalid audience")
    elif token_aud not in valid_audiences:
        raise JWTError("Invalid audience")
    return payload


@dataclass
class TokenResult:
    """Result of decoding and resolving a JWT token."""
    user: User
    is_impersonation: bool = False
    original_user_id: Optional[str] = None
    impersonation_session_id: Optional[str] = None


def decode_and_resolve_user(
    token: str,
    db: Session,
    request: Optional[Request] = None,
) -> TokenResult:
    """
    Decode a JWT (HS256 or Auth0 RS256), validate impersonation session
    if applicable, and resolve the User from the database.

    If ``request`` is provided, stores impersonation metadata in
    ``request.state`` for downstream audit logging.

    Raises:
        HTTPException: On any authentication / validation failure.
    """
    user_id = None
    auth0_id = None
    is_impersonation = False
    original_user_id = None
    impersonation_session_id = None

    # 1. Decode token — try HS256 first (email/password + impersonation), fallback to Auth0 RS256
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        is_impersonation = payload.get("is_impersonation", False)
        if is_impersonation:
            original_user_id = payload.get("original_user_id")
            impersonation_session_id = payload.get("impersonation_session_id")
    except JWTError:
        try:
            payload = decode_auth0_token(token)
            auth0_id = payload.get("sub")
        except Exception as e:
            logger.error(f"Auth0 token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

    if not auth0_id and not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'sub' claim",
        )

    # 2. Validate impersonation session
    if is_impersonation and user_id:
        if impersonation_session_id:
            try:
                session_uuid = (
                    UUID(impersonation_session_id)
                    if isinstance(impersonation_session_id, str)
                    else impersonation_session_id
                )
                impersonation_session = db.query(ImpersonationSession).filter(
                    ImpersonationSession.id == session_uuid,
                    ImpersonationSession.status == "active",
                ).first()

                if not impersonation_session:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Impersonation session has ended",
                    )

                # Store in request state for audit logging
                if request is not None:
                    request.state.original_user_id = original_user_id
                    request.state.impersonation_session_id = impersonation_session_id
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid impersonation session",
                )

        user = db.query(User).filter(User.id == user_id).first()
    else:
        # Normal auth — resolve by user_id or auth0_id
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
        else:
            user = db.query(User).filter(User.auth0_id == auth0_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return TokenResult(
        user=user,
        is_impersonation=is_impersonation,
        original_user_id=original_user_id,
        impersonation_session_id=impersonation_session_id,
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.
    
    Supports two authentication methods:
    1. Bearer token (Authorization header) - for API clients like Postman
    2. Session-based (cookies) - for web frontend
    
    Priority: Bearer token is checked first, then session.
    
    Also handles impersonation tokens:
    - If token has is_impersonation flag, uses impersonated user ID from 'sub'
    - Verifies impersonation session is still active
    - Stores original user ID in request state for audit logging
    
    Raises:
        HTTPException: If user is not authenticated
    """
    result = None

    # Method 1: Check for Bearer token in Authorization header
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        result = decode_and_resolve_user(token, db, request)

    # Method 2: Check for session-based authentication
    if result is None:
        user_session = request.session.get('user')
        if user_session:
            auth0_id = user_session.get('auth0_id')
            if auth0_id:
                user = db.query(User).filter(User.auth0_id == auth0_id).first()
                if user:
                    result = TokenResult(user=user)

    # If no authentication method worked
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    user = result.user

    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deleted"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    impersonation_note = f" (impersonating as {user.email})" if result.is_impersonation else ""
    logger.debug(f"User authenticated: {user.email}, role: {user.role}{impersonation_note}")
    return user


def require_role(allowed_roles: List[UserRole]):
    """
    Dependency factory to require specific roles.
    
    Usage:
        @router.get("/admin-only")
        def admin_route(user: User = Depends(require_role([UserRole.ADMIN, UserRole.SUPER_ADMIN]))):
            ...
    """
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        return user
    
    return role_checker


def is_token_expired(token: dict) -> bool:
    """
    Check if Auth0 token is expired.
    
    Args:
        token: Token dictionary from Auth0
        
    Returns:
        bool: True if token is expired, False otherwise
    """
    try:
        # Get access token
        access_token = token.get('access_token')
        if not access_token:
            return True
        
        # Decode token WITHOUT verifying signature – we only need the `exp` claim.
        # python-jose requires a key for decode(), so we use get_unverified_claims instead.
        decoded = jwt.get_unverified_claims(access_token)
        
        # Check expiry
        exp = decoded.get('exp')
        if not exp:
            return True
        
        # Compare with current time
        current_time = datetime.now(timezone.utc).timestamp()
        return exp < current_time
        
    except (JWTError, KeyError, ValueError):
        return True


def get_token_expiry_time(token: dict) -> Optional[datetime]:
    """
    Get token expiry time.
    
    Args:
        token: Token dictionary from Auth0
        
    Returns:
        datetime: Expiry time or None if not found
    """
    try:
        access_token = token.get('access_token')
        if not access_token:
            return None
        
        # Decode token without verifying signature to read `exp` claim
        decoded = jwt.get_unverified_claims(access_token)
        
        exp = decoded.get('exp')
        if not exp:
            return None
        
        return datetime.utcfromtimestamp(exp)
        
    except (JWTError, KeyError, ValueError):
        return None


def get_original_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get the original superadmin user when impersonating.
    
    This function extracts the original user ID from the request state
    (set by get_current_user when impersonation is detected) and returns
    the original user object.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        User: The original superadmin user, or None if not impersonating
    """
    original_user_id = getattr(request.state, 'original_user_id', None)
    if not original_user_id:
        return None
    
    try:
        user_uuid = UUID(original_user_id) if isinstance(original_user_id, str) else original_user_id
        return db.query(User).filter(User.id == user_uuid).first()
    except (ValueError, TypeError):
        return None


