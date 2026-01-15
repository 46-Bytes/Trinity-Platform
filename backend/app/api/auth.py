"""
Authentication API routes using Auth0 Universal Login and email/password.
"""
import logging
from fastapi import APIRouter, Depends, Request, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from urllib.parse import urlencode, quote_plus
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from jose import jwt, JWTError
from ..database import get_db
from ..services.auth_service import AuthService
from ..services.login_check import check_user_login_eligibility
from ..services.audit_service import AuditService
from ..config import settings
from ..utils.auth import get_current_user, get_token_expiry_time, get_original_user
from ..utils.password import hash_password, verify_password
from ..models.user import User
from ..models.firm import Firm
from ..models.impersonation import ImpersonationSession
from uuid import UUID

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Create OAuth client
oauth = AuthService.create_oauth_client()


@router.get("/login")
async def login(request: Request, force_login: bool = Query(False, description="Force Auth0 to show login page")):
    """
    Initiate Auth0 Universal Login flow.
    
    This endpoint redirects the user to Auth0's Universal Login page.
    
    Flow:
    1. User clicks "Login" on your frontend
    2. Frontend redirects to this endpoint
    3. This endpoint redirects to Auth0 Universal Login
    4. User logs in on Auth0's hosted page
    5. Auth0 redirects back to /callback
    
    Args:
        force_login: If True, forces Auth0 to show login page (prompt=login)
                    Useful when user needs to try different credentials
    """
    # Build the callback URL
    redirect_uri = request.url_for('callback')
    
    # Prepare authorization parameters
    auth_params = {}
    if force_login:
        auth_params['prompt'] = 'login'
    
    # Redirect to Auth0 Universal Login
    # Explicitly skip consent screen and don't request API access
    return await oauth.auth0.authorize_redirect(
        request,
        redirect_uri=str(redirect_uri),
        **auth_params
        # Don't request any API audience - only user info
        # This prevents the "Authorize App" consent screen
    )


@router.get("/callback", name="callback")
async def callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Auth0 callback after successful authentication.
    
    This endpoint:
    1. Receives the authorization code from Auth0
    2. Exchanges it for an access token
    3. Gets user information
    4. Creates or updates user in database
    5. Creates a session
    6. Redirects to frontend
    """
    try:
        # Get the access token from Auth0
        token = await oauth.auth0.authorize_access_token(request)
        # Get user information from the token
        user_info = token.get('userinfo')
        # If userinfo is not in token, fetch it from Auth0 userinfo endpoint
        if not user_info:
            access_token = token.get('access_token')
            if access_token:
                try:
                    # Fetch user info from Auth0 using requests (synchronous, but works)
                    import requests
                    response = requests.get(
                        f'https://{settings.AUTH0_DOMAIN}/userinfo',
                        headers={'Authorization': f'Bearer {access_token}'}
                    )
                    if response.status_code == 200:
                        user_info = response.json()
                except Exception as e:
                    print(f"Error fetching userinfo: {str(e)}")
        
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to get user information")
            
    
        
        # Extract username from ID token custom claim
        id_token = token.get('id_token')
        username_from_token = None
        if id_token:
            try:
                # Decode ID token to get custom claims
                id_token_payload = jwt.get_unverified_claims(id_token)

                
                # Extract username from custom claim
                username_from_token = id_token_payload.get(settings.AUTH0_USERNAME_NAMESPACE)
                
            except Exception as e:
                import traceback
                logger.error(f"  [SIGNUP/LOGIN] Traceback: {traceback.format_exc()}")
        else:
            logger.warning(f"  [SIGNUP/LOGIN] No ID token found in Auth0 response")
        
        # Add username to user_info if found in token
        if username_from_token:
            user_info['username'] = username_from_token
        
        # Create or update user in database
        user = AuthService.get_or_create_user(db, user_info)
        
        # Check if user is eligible to login (firm revoked, user suspended, etc.)
        can_login, error_message = check_user_login_eligibility(db, user)
        if not can_login:
            if error_message == "firm_revoked":
                logger.warning(f"Login blocked: Firm revoked for user {user.email}")
                # Logout from Auth0 first, then redirect to login with error
                # This ensures user can try different credentials
                params = {
                    'returnTo': f"{settings.FRONTEND_URL}/login?error=firm_revoked",
                    'client_id': settings.AUTH0_CLIENT_ID,
                }
                logout_url = f"https://{settings.AUTH0_DOMAIN}/v2/logout?{urlencode(params, quote_via=quote_plus)}"
                return RedirectResponse(url=logout_url, status_code=302)
            else:
                # User suspended or other reason
                logger.warning(f"Login blocked: {error_message} for user {user.email}")
                params = {
                    'returnTo': f"{settings.FRONTEND_URL}/login?error=account_suspended",
                    'client_id': settings.AUTH0_CLIENT_ID,
                }
                logout_url = f"https://{settings.AUTH0_DOMAIN}/v2/logout?{urlencode(params, quote_via=quote_plus)}"
                return RedirectResponse(url=logout_url, status_code=302)
        
        # Get the ID token (JWT) from Auth0 - frontend will use this
        if not id_token:
            logger.error(f"  No id_token in Auth0 response")
            raise Exception("No id_token received from Auth0")
        
        # URL encode the token to handle special characters
        encoded_token = quote_plus(id_token)
        
        # Redirect to frontend callback page with token
        # Frontend will store token in localStorage and redirect to dashboard
        callback_url = f"{settings.FRONTEND_URL}/auth/callback?token={encoded_token}"
        
        response = RedirectResponse(
            url=callback_url,
            status_code=302
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        import traceback
        traceback.print_exc()
        # Redirect to frontend with error
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error=authentication_failed",
            status_code=302
        )


@router.get("/logout")
async def logout(request: Request):
    """
    Logout user from Auth0 and redirect back to frontend.
    
    This endpoint:
    1. Redirects to Auth0 logout endpoint
    2. Auth0 clears its session and redirects back to frontend login page
    
    Note: Frontend clears localStorage token before calling this endpoint
    """
    # Build Auth0 logout URL
    params = {
        'returnTo': f"{settings.FRONTEND_URL}/login",  # Redirect to login page after logout
        'client_id': settings.AUTH0_CLIENT_ID,
    }
    
    logout_url = f"https://{settings.AUTH0_DOMAIN}/v2/logout?{urlencode(params, quote_via=quote_plus)}"
    
    return RedirectResponse(url=logout_url)


@router.get("/user")
async def get_current_user_endpoint(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user from Authorization header.
    
    Expects: Authorization: Bearer <id_token>
    Returns user information if authenticated, 401 if not.
    Also handles impersonation tokens.
    """
    # Get token from Authorization header
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.error(f"  No Authorization header or invalid format")
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.split(' ')[1]
    
    try:
        user_id = None
        auth0_id = None
        is_impersonation = False
        original_user_id = None
        impersonation_session_id = None
        
        # Try to decode with SECRET_KEY first (for email/password and impersonation tokens)
        try:
            payload = jwt.decode(token, settings.SECRET_KEY or 'your-secret-key-change-in-production', algorithms=["HS256"])
            user_id = payload.get('sub')  # For email/password and impersonation tokens, sub is user ID
            is_impersonation = payload.get('is_impersonation', False)
            if is_impersonation:
                original_user_id = payload.get('original_user_id')
                impersonation_session_id = payload.get('impersonation_session_id')
        except JWTError:
            # If verification fails, try unverified (Auth0 tokens)
            payload = jwt.get_unverified_claims(token)
            auth0_id = payload.get('sub')  # For Auth0 tokens, sub is auth0_id
            # Check for impersonation flag (shouldn't happen with Auth0 tokens, but check anyway)
            is_impersonation = payload.get('is_impersonation', False)
            if is_impersonation:
                original_user_id = payload.get('original_user_id')
                impersonation_session_id = payload.get('impersonation_session_id')
        
        if not auth0_id and not user_id:
            logger.error(f"  No 'sub' claim in token")
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Handle impersonation
        if is_impersonation and user_id:
            # Verify impersonation session is still active
            if impersonation_session_id:
                try:
                    from uuid import UUID
                    session_uuid = UUID(impersonation_session_id) if isinstance(impersonation_session_id, str) else impersonation_session_id
                    impersonation_session = db.query(ImpersonationSession).filter(
                        ImpersonationSession.id == session_uuid,
                        ImpersonationSession.status == 'active'
                    ).first()
                    
                    if not impersonation_session:
                        raise HTTPException(
                            status_code=401,
                            detail="Impersonation session has ended"
                        )
                except (ValueError, TypeError):
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid impersonation session"
                    )
            
            # Use impersonated user ID from token
            user = db.query(User).filter(User.id == user_id).first()
        else:
            # Normal authentication - find user by auth0_id or user_id
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
            else:
                user = db.query(User).filter(User.auth0_id == auth0_id).first()
        
        if not user:
            identifier = user_id if user_id else auth0_id
            logger.error(f"  User not found in database for identifier: {identifier}")
            raise HTTPException(status_code=401, detail="User not found")
        
        user_dict = user.to_dict()
        return {
            "authenticated": True,
            "user": user_dict
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"  Token validation error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/check")
async def check_auth(request: Request):
    """
    Quick check if user is authenticated.
    
    Returns:
        dict: {"authenticated": bool}
    """
    user_session = request.session.get('user')
    print(f"Check endpoint - Session keys: {list(request.session.keys())}")
    print(f"Check endpoint - User session: {user_session is not None}")
    return {
        "authenticated": user_session is not None,
        "session_keys": list(request.session.keys()),
        "has_user": 'user' in request.session
    }


# ==================== Email/Password Login ====================

class EmailPasswordLogin(BaseModel):
    """Schema for email/password login."""
    email: EmailStr
    password: str


@router.post("/login-email")
async def login_email_password(
    login_data: EmailPasswordLogin,
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Login with email and password.
    
    This endpoint:
    1. Finds user by email
    2. Verifies password
    3. Returns user info with role from database
    """
    # Find user by email
    user = db.query(User).filter(User.email == login_data.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user has a password (email/password users)
    if not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account does not have a password set. Please use Auth0 login."
        )
    
    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user is eligible to login (firm revoked, user suspended, etc.)
    can_login, error_message = check_user_login_eligibility(db, user)
    if not can_login:
        if error_message == "firm_revoked":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Firm account has been revoked"
            )
        else:
            # User suspended or other reason
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_message
            )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create a simple JWT token for the frontend
    token_secret = settings.SECRET_KEY or 'your-secret-key-change-in-production'
    token_expiry = datetime.utcnow() + timedelta(days=7)
    
    token_payload = {
        "sub": str(user.id),  # Use user ID instead of auth0_id
        "email": user.email,
        "role": user.role.value if user.role else "advisor",
        "exp": token_expiry
    }
    
    token = jwt.encode(token_payload, token_secret, algorithm="HS256")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict()
    }


@router.post("/stop-impersonation")
async def stop_impersonation(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stop impersonation and return to original superadmin user.
    
    This endpoint:
    1. Verifies the current session is an impersonation session
    2. Marks the impersonation session as ended
    3. Generates a new normal token for the original superadmin
    4. Returns the new token
    """
    # Get token from Authorization header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    token = auth_header.split(' ')[1]
    
    try:
        # Decode token to check for impersonation flag
        try:
            payload = jwt.decode(token, settings.SECRET_KEY or 'your-secret-key-change-in-production', algorithms=["HS256"])
        except JWTError:
            # Try unverified for Auth0 tokens (though impersonation should use SECRET_KEY)
            payload = jwt.get_unverified_claims(token)
        
        is_impersonation = payload.get('is_impersonation', False)
        original_user_id = payload.get('original_user_id')
        impersonation_session_id = payload.get('impersonation_session_id')
        
        if not is_impersonation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not currently impersonating"
            )
        
        if not original_user_id or not impersonation_session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid impersonation token"
            )
        
        # Get original user
        original_user = db.query(User).filter(User.id == UUID(original_user_id)).first()
        if not original_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original user not found"
            )
        
        # Mark impersonation session as ended
        session_uuid = UUID(impersonation_session_id) if isinstance(impersonation_session_id, str) else impersonation_session_id
        impersonation_session = db.query(ImpersonationSession).filter(
            ImpersonationSession.id == session_uuid
        ).first()
        
        if impersonation_session:
            impersonation_session.status = 'ended'
            impersonation_session.ended_at = datetime.utcnow()
            db.commit()
        
        # Generate new normal token for original superadmin
        token_secret = settings.SECRET_KEY or 'your-secret-key-change-in-production'
        token_expiry = datetime.utcnow() + timedelta(days=7)
        
        token_payload = {
            "sub": str(original_user.id),
            "email": original_user.email,
            "role": original_user.role.value if original_user.role else "super_admin",
            "exp": int(token_expiry.timestamp())
        }
        
        new_token = jwt.encode(token_payload, token_secret, algorithm="HS256")
        
        # Log impersonation end
        AuditService.log_impersonation_end(
            session_id=session_uuid,
            original_user_id=original_user.id,
            db=db
        )
        
        return {
            "access_token": new_token,
            "token_type": "bearer",
            "user": original_user.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping impersonation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop impersonation"
        )


@router.get("/impersonation-status")
async def get_impersonation_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current impersonation status.
    
    Returns information about whether the current session is an impersonation
    session, including both the original superadmin and impersonated user info.
    """
    # Get token from Authorization header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return {
            "is_impersonating": False
        }
    
    token = auth_header.split(' ')[1]
    
    try:
        # Decode token to check for impersonation flag
        try:
            payload = jwt.decode(token, settings.SECRET_KEY or 'your-secret-key-change-in-production', algorithms=["HS256"])
        except JWTError:
            # Try unverified for Auth0 tokens
            payload = jwt.get_unverified_claims(token)
        
        is_impersonation = payload.get('is_impersonation', False)
        original_user_id = payload.get('original_user_id')
        impersonation_session_id = payload.get('impersonation_session_id')
        
        if not is_impersonation:
            return {
                "is_impersonating": False
            }
        
        # Get original user
        original_user = None
        if original_user_id:
            original_user = db.query(User).filter(User.id == UUID(original_user_id)).first()
        
        return {
            "is_impersonating": True,
            "impersonated_user": current_user.to_dict(),
            "original_user": original_user.to_dict() if original_user else None,
            "impersonation_session_id": impersonation_session_id
        }
        
    except Exception as e:
        logger.error(f"Error checking impersonation status: {str(e)}")
        return {
            "is_impersonating": False
        }


