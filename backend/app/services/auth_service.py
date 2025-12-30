"""
Auth0 authentication service.
"""
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from datetime import datetime
from ..models.user import User, UserRole
from ..schemas.user import UserCreate
from ..config import settings
import requests


class AuthService:
    """Service for handling Auth0 authentication and user management."""
    
    @staticmethod
    def create_oauth_client():
        """
        Create and configure OAuth client for Auth0.
        
        Returns:
            OAuth: Configured OAuth client
        """
        oauth = OAuth()
        
        oauth.register(
            name='auth0',
            client_id=settings.AUTH0_CLIENT_ID,
            client_secret=settings.AUTH0_CLIENT_SECRET,
            server_metadata_url=f'https://{settings.AUTH0_DOMAIN}/.well-known/openid-configuration',
            client_kwargs={
                'scope': 'openid profile email',  # Only request user info, not Management API
            },
            # Don't set audience - this prevents API consent screen
            # audience=None  # Explicitly no API access
        )
        
        return oauth
    
    @staticmethod
    def extract_role_from_auth0(user_info: dict) -> UserRole | None:
        """
        Extract user role from Auth0 user info.
        
        Checks in order:
        1. app_metadata.role
        2. user_metadata.role
        3. Returns None if no role found (don't default)
        
        Args:
            user_info: User information from Auth0
            
        Returns:
            UserRole | None: User role if found in Auth0, None otherwise
        """
        # Check app_metadata first (typically set by admin)
        app_metadata = user_info.get('app_metadata', {})
        role_str = app_metadata.get('role')
        
        if not role_str:
            # Check user_metadata
            user_metadata = user_info.get('user_metadata', {})
            role_str = user_metadata.get('role')
        
        if role_str:
            # Try to match the role
            role_str_lower = role_str.lower()
            if role_str_lower == 'super_admin':
                return UserRole.SUPER_ADMIN
            elif role_str_lower == 'admin':
                return UserRole.ADMIN
            elif role_str_lower == 'client':
                return UserRole.CLIENT
            elif role_str_lower == 'advisor':
                return UserRole.ADVISOR
            elif role_str_lower == 'firm_admin':
                return UserRole.FIRM_ADMIN
            elif role_str_lower == 'firm_advisor':
                return UserRole.FIRM_ADVISOR
        
        # Return None if no role found - don't default
        return None
    
    @staticmethod
    def get_or_create_user(db: Session, user_info: dict) -> User:
        """
        Get existing user or create new user from Auth0 user info.
        
        Handles account linking: If a user with the same email exists but different auth0_id
        (e.g., signed up with email/password, now logging in with Google), updates the auth0_id
        to link the accounts.
        
        Args:
            db: Database session
            user_info: User information from Auth0
            
        Returns:
            User: User object
        """
        auth0_id = user_info.get('sub')
        email = user_info.get('email')
        
        # Extract role from Auth0 (may be None if not set in Auth0)
        auth0_role = AuthService.extract_role_from_auth0(user_info)
        
        # Try to find existing user by auth0_id first
        user = db.query(User).filter(User.auth0_id == auth0_id).first()
        
        # If not found by auth0_id, check by email (for account linking)
        if not user and email:
            user = db.query(User).filter(User.email == email).first()
            if user:
                # Account linking: User exists with same email but different auth0_id
                # Update the auth0_id to link the accounts
                print(f"🔗 Linking accounts: {user.auth0_id} -> {auth0_id} for {email}")
                user.auth0_id = auth0_id
        
        if user:
            # Update existing user information
            user.email = email
            user.name = user_info.get('name')
            user.given_name = user_info.get('given_name')
            user.family_name = user_info.get('family_name')
            
            # Extract username from Auth0 - check multiple possible fields
            # Auth0 signup form might store username in different places:
            # 1. user_metadata.username (custom field from signup form)
            # 2. nickname (Auth0 default field, but defaults to email prefix)
            # 3. preferred_username (sometimes used by Auth0)
            user_metadata = user_info.get('user_metadata', {})
            app_metadata = user_info.get('app_metadata', {})
            nickname = user_info.get('nickname')
            preferred_username = user_info.get('preferred_username')
            
            # Log all possible username fields for debugging
            print(f"🔍 Auth0 username fields:")
            print(f"   - user_metadata: {user_metadata}")
            print(f"   - app_metadata: {app_metadata}")
            print(f"   - nickname: {nickname}")
            print(f"   - preferred_username: {preferred_username}")
            print(f"   - name: {user_info.get('name')}")
            
            # Priority: user_metadata.username > preferred_username > nickname (if not email prefix) > name
            email_prefix = email.split('@')[0] if email else None
            username = (
                user_metadata.get('username') or 
                preferred_username or 
                (nickname if nickname and '@' not in nickname and nickname != email_prefix else None) or
                user_info.get('name')
            )
            
            # Only update nickname if we found a valid username (not just email prefix)
            if username:
                user.nickname = username
                print(f"🔤 Updated nickname to: {username}")
            else:
                print(f"⚠️  No valid username found in Auth0 data, keeping existing nickname: {user.nickname}")
            
            user.picture = user_info.get('picture')
            
            # IMPORTANT: Only update email_verified if it's True (don't unverify)
            # If user already has verified email, keep it verified
            # Only update if Auth0 says it's verified (prevents unverifying)
            auth0_email_verified = user_info.get('email_verified', False)
            if auth0_email_verified:
                user.email_verified = True  # Update to verified
            # If False, don't change existing verified status (preserve verified state)
            
            # IMPORTANT: Only update role from Auth0 if Auth0 has a role set
            # This preserves manually set roles in the database
            if auth0_role is not None:
                print(f"🔄 Updating role from Auth0: {user.role.value} -> {auth0_role.value}")
                user.role = auth0_role
            else:
                print(f"✅ Preserving existing role: {user.role.value} (no role in Auth0 metadata)")
            
            user.last_login = datetime.utcnow()
            user.updated_at = datetime.utcnow()
        else:
            # Create new user
            # Use Auth0 role if available, otherwise default to CLIENT (safer default than advisor)
            default_role = auth0_role if auth0_role is not None else UserRole.CLIENT
            print(f"👤 Creating new user with role: {default_role.value} (from Auth0: {auth0_role.value if auth0_role else 'None'})")
            
            # Extract username from Auth0 - check multiple possible fields
            user_metadata = user_info.get('user_metadata', {})
            app_metadata = user_info.get('app_metadata', {})
            nickname = user_info.get('nickname')
            preferred_username = user_info.get('preferred_username')
            
            # Log all possible username fields for debugging
            print(f"🔍 Auth0 username fields (new user):")
            print(f"   - user_metadata: {user_metadata}")
            print(f"   - app_metadata: {app_metadata}")
            print(f"   - nickname: {nickname}")
            print(f"   - preferred_username: {preferred_username}")
            print(f"   - name: {user_info.get('name')}")
            
            # Priority: user_metadata.username > preferred_username > nickname (if not email prefix) > name
            email_prefix = email.split('@')[0] if email else None
            username = (
                user_metadata.get('username') or 
                preferred_username or 
                (nickname if nickname and '@' not in nickname and nickname != email_prefix else None) or
                user_info.get('name')
            )
            
            print(f"🔤 New user nickname: {username}")
            
            user = User(
                auth0_id=auth0_id,
                email=email,
                name=user_info.get('name'),
                given_name=user_info.get('given_name'),
                family_name=user_info.get('family_name'),
                nickname=username,
                picture=user_info.get('picture'),
                email_verified=user_info.get('email_verified', False),
                role=default_role,  # Use Auth0 role or default to CLIENT
                last_login=datetime.utcnow(),
            )
            db.add(user)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def get_user_by_auth0_id(db: Session, auth0_id: str) -> User:
        """
        Get user by Auth0 ID.
        
        Args:
            db: Database session
            auth0_id: Auth0 user ID
            
        Returns:
            User: User object or None
        """
        return db.query(User).filter(User.auth0_id == auth0_id).first()
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User:
        """
        Get user by email.
        
        Args:
            db: Database session
            email: User email
            
        Returns:
            User: User object or None
        """
        return db.query(User).filter(User.email == email).first()


