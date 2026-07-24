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
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from ..database import get_db
from ..services.auth_service import AuthService
from ..services.login_check import check_user_login_eligibility
from ..services.audit_service import AuditService
from ..services.self_service import consume_intent, find_usable_intent, get_active_subscription
from ..services.team_service import mark_member_active
from ..config import settings
from ..utils.auth import get_current_user, get_token_expiry_time, get_original_user, decode_auth0_token, decode_and_resolve_user
from ..utils.password import hash_password, verify_password
from ..models.user import User, UserRole
from ..models.firm import Firm
from ..models.impersonation import ImpersonationSession
from uuid import UUID
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Create OAuth client
oauth = AuthService.create_oauth_client()


@router.get("/login")
async def login(
    request: Request,
    force_login: bool = Query(False, description="Force Auth0 to show login page"),
    screen_hint: Optional[str] = Query(None, description="Pass 'signup' to open Auth0's signup screen"),
    intent: Optional[str] = Query(None, description="Self-service signup intent ID (Feature 7)"),
):
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
        screen_hint: 'signup' opens Auth0's registration screen instead of login.
                    Used by the self-service business owner funnel.
        intent: Self-service signup intent ID. Stashed in the session so the
                callback can apply the owner's program and business name. The
                callback also matches on email, so losing the session only
                costs precision, not correctness.
    """
    # Build the callback URL
    redirect_uri = request.url_for('callback')

    # Prepare authorization parameters
    auth_params = {}
    if force_login:
        auth_params['prompt'] = 'login'
    if screen_hint == 'signup':
        auth_params['screen_hint'] = 'signup'

    # Carry the self-service signup intent across the Auth0 round trip.
    request.session.pop('signup_intent_id', None)
    if intent:
        request.session['signup_intent_id'] = intent

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
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
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
        
        # Self-service (Feature 7): if this email started a signup on our site,
        # apply their intent so they are created as a self-service business
        # owner rather than falling through to the ADVISOR default.
        auth0_email = user_info.get('email', '')
        signup_intent = find_usable_intent(
            db,
            email=auth0_email,
            intent_id=request.session.pop('signup_intent_id', None),
        )
        # Capture this before get_or_create_user, which creates the row.
        is_new_account = not AuthService.get_user_by_email(db, auth0_email) if auth0_email else False

        # Create or update user in database
        user = AuthService.get_or_create_user(
            db, user_info,
            default_role=UserRole.CLIENT if signup_intent else None,
        )

        was_new_signup = False
        if signup_intent:
            # Only apply to a brand new account - an intent must never be able
            # to re-role somebody who already had one.
            if is_new_account:
                consume_intent(db, signup_intent, user)
                was_new_signup = True
            else:
                logger.warning(
                    "Signup intent %s matched an existing account (%s); ignoring",
                    signup_intent.id, user.email,
                )

        # A team member's first login flips their membership to active.
        if user.role == UserRole.TEAM_MEMBER:
            mark_member_active(db, user)

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
        
        # Create a custom HS256 JWT so we fully control the expiry.
        # (The raw Auth0 id_token has its own expiry set in the Auth0 dashboard
        # and cannot be shortened from the backend.)
        token_expiry = datetime.now(timezone.utc) + timedelta(days=1)
        token_payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value if user.role else "advisor",
            "exp": token_expiry,
        }
        custom_token = jwt.encode(token_payload, settings.SECRET_KEY, algorithm="HS256")
        encoded_token = quote_plus(custom_token)

        # Redirect to frontend callback page with token
        # Frontend will store token in localStorage and redirect to dashboard
        callback_url = f"{settings.FRONTEND_URL}/auth/callback?token={encoded_token}"

        # A self-service owner who has not paid yet goes to checkout, not the
        # dashboard - their workspace does not exist until the subscription is
        # active. `next` is read by the frontend AuthCallback page.
        if was_new_signup or (user.role == UserRole.CLIENT and user.is_self_service):
            if not get_active_subscription(db, user.id):
                program = signup_intent.program if signup_intent else ""
                next_path = f"/onboarding/checkout?program={program}" if program else "/onboarding/checkout"
                callback_url += f"&next={quote_plus(next_path)}"

        response = RedirectResponse(
            url=callback_url,
            status_code=302
        )
        
        return response
        
    except Exception as e:
        logger.exception("Callback error")
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
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.split(' ')[1]

    try:
        result = decode_and_resolve_user(token, db)
        user_dict = result.user.to_dict()
        return {
            "authenticated": True,
            "user": user_dict
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token validation error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/check")
async def check_auth(request: Request):
    """
    Quick check if user is authenticated.
    
    Returns:
        dict: {"authenticated": bool}
    """
    user_session = request.session.get('user')
    return {
        "authenticated": user_session is not None,
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
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    
    # Create a simple JWT token for the frontend
    token_secret = settings.SECRET_KEY
    token_expiry = datetime.now(timezone.utc) + timedelta(days=1)
    
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
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except JWTError:
            # Impersonation tokens are always HS256 — if decode fails, reject
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid impersonation token"
            )

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
            impersonation_session.ended_at = datetime.now(timezone.utc)
            db.commit()
        
        # Generate new normal token for original superadmin
        token_secret = settings.SECRET_KEY
        token_expiry = datetime.now(timezone.utc) + timedelta(days=7)
        
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
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except JWTError:
            # Auth0 tokens won't have impersonation flags — safe to return false
            return {"is_impersonating": False}

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


