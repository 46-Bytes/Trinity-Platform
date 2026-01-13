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
from jose import jwt
from ..database import get_db
from ..services.auth_service import AuthService
from ..config import settings
from ..utils.auth import get_current_user, get_token_expiry_time
from ..utils.password import hash_password, verify_password
from ..models.user import User
from ..models.firm import Firm

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
        
        # Check if user's firm is revoked
        if user.firm_id:
            firm = db.query(Firm).filter(Firm.id == user.firm_id).first()
            if firm and not firm.is_active:
                logger.warning(f"Login blocked: Firm {firm.id} is revoked for user {user.email}")
                # Logout from Auth0 first, then redirect to login with error
                # This ensures user can try different credentials
                params = {
                    'returnTo': f"{settings.FRONTEND_URL}/login?error=firm_revoked",
                    'client_id': settings.AUTH0_CLIENT_ID,
                }
                logout_url = f"https://{settings.AUTH0_DOMAIN}/v2/logout?{urlencode(params, quote_via=quote_plus)}"
                return RedirectResponse(url=logout_url, status_code=302)
        
        if user.role.value == 'client':
            firms_with_client = db.query(Firm).filter(
                text("clients @> ARRAY[:user_id]::uuid[]").bindparams(user_id=user.id)
            ).all()
            for firm in firms_with_client:
                if not firm.is_active:
                    logger.warning(f"Login blocked: Client {user.email} is in revoked firm {firm.id}")
                    # This ensures user can try different credentials
                    params = {
                        'returnTo': f"{settings.FRONTEND_URL}/login?error=firm_revoked",
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
    """
    # Get token from Authorization header
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.error(f"  No Authorization header or invalid format")
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.split(' ')[1]
    
    try:
        # Decode the ID token to get user info (no signature verification for simplicity)
        
        payload = jwt.get_unverified_claims(token)
        
        # Get auth0_id from the 'sub' claim
        auth0_id = payload.get('sub')
        
        # Extract username from custom claim for logging
        username = payload.get(settings.AUTH0_USERNAME_NAMESPACE)
        
        if not auth0_id:
            logger.error(f"  No 'sub' claim in token")
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Find user in database
        user = db.query(User).filter(User.auth0_id == auth0_id).first()
        if not user:
            logger.error(f"  User not found in database for auth0_id: {auth0_id}")
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
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended"
        )
    
    # Check if user's firm is revoked
    # This applies to: firm_admin, firm_advisor, and clients with firm_id
    if user.firm_id:
        firm = db.query(Firm).filter(Firm.id == user.firm_id).first()
        if firm and not firm.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Firm account has been revoked"
            )
    
    if user.role.value == 'client':
        # Query all firms to check if this client is in any firm's clients array
        firms_with_client = db.query(Firm).filter(
            text("clients @> ARRAY[:user_id]::uuid[]").bindparams(user_id=user.id)
        ).all()
        for firm in firms_with_client:
            if not firm.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Firm account has been revoked"
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


