"""
Auth0 authentication service.
"""
import logging
from typing import Optional
from authlib.integrations.starlette_client import OAuth
from .auth0_management import Auth0Management
from sqlalchemy.orm import Session
from datetime import datetime
from ..models.user import User, UserRole
from ..config import settings

logger = logging.getLogger(__name__)


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
        
        # Get username directly from Auth0 (source of truth)
        username = user_info.get('username') or user_info.get('nickname')
        
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
            # Update existing user information (DATABASE IS SOURCE OF TRUTH FOR ROLE)
            user.email = email
            
            if not user.first_name:
                first_name = user_info.get('first_name')
                if first_name:
                    user.first_name = first_name
            
            if not user.last_name:
                last_name = user_info.get('last_name')
                if last_name:
                    user.last_name = last_name
            
            # Always update username from Auth0 (source of truth)
            if username:
                if hasattr(user, 'username'):
                    user.username = username
                user.nickname = username
            
            name_parts = []
            if user.first_name:
                name_parts.append(user.first_name)
            if user.last_name:
                name_parts.append(user.last_name)
            
            if name_parts:
                user.name = " ".join(name_parts)
            elif username:
                user.name = username
            elif not user.name:
                user.name = email
            
            auth0_picture = user_info.get('picture')
            current_picture = user.picture
            
            # Check if current picture is user-uploaded (stored in our filesystem in profilepicture directory)
            is_user_uploaded = current_picture and (
                f'/users/{str(user.id)}/profilepicture/' in current_picture or
                current_picture.startswith('/files/uploads/users/') and '/profilepicture/' in current_picture
            )
            
            if is_user_uploaded:
                # Never overwrite user-uploaded pictures
                logger.info(f"  [USER_UPDATE] Preserving user-uploaded picture (not overwriting with Auth0)")
            elif auth0_picture:
                # Only update if no existing picture or existing picture is from Auth0
                user.picture = auth0_picture
                logger.info(f"  [USER_UPDATE] Updated picture from Auth0")
            else:
                logger.info(f"  [USER_UPDATE] No picture from Auth0, preserving existing picture")
            
            auth0_email_verified = user_info.get('email_verified', False)
            if auth0_email_verified:
                user.email_verified = True  # Update to verified

            # IMPORTANT: Do NOT overwrite existing user's role from Auth0.
            # The database role is the source of truth once the user exists.
            # This ensures roles set via the app (e.g., firm_admin) are preserved
            # even if Auth0 metadata has a different or stale role.
            if auth0_role is not None and user.role is None:
                # Extremely rare: backfill role only if it's somehow missing in DB
                print(f" Backfilling missing role from Auth0: {auth0_role.value}")
                user.role = auth0_role
            
            user.last_login = datetime.utcnow()
            user.updated_at = datetime.utcnow()
        else:
            # Create new user
            # Use Auth0 role if available, otherwise default to ADVISOR
            default_role = auth0_role if auth0_role is not None else UserRole.ADVISOR
            print(f"👤 Creating new user with role: {default_role.value} (from Auth0: {auth0_role.value if auth0_role else 'None'})")
            
            # Username comes from Auth0 (already extracted above)

            first_name = user_info.get('first_name') or user_info.get('given_name')
            last_name = user_info.get('last_name') or user_info.get('family_name')
            
            logger.info(f"  [USER_CREATE] Creating user with - email: {email}, username: {username}, first_name: {first_name}, last_name: {last_name}, role: {default_role.value}")
            
            # Determine the name to use (username from Auth0, or email as fallback)
            display_name = username or email
            

            user_data = {
                'auth0_id': auth0_id,
                'email': email,
                'name': display_name,
                'first_name': first_name,  
                'last_name': last_name,
                'picture': user_info.get('picture'),
                'email_verified': user_info.get('email_verified', False),
                'role': default_role,
                'last_login': datetime.utcnow(),
            }
            
            # Add username from Auth0 if available
            if username:
                if hasattr(User, 'username'):
                    user_data['username'] = username
                user_data['nickname'] = username
            
            user = User(**user_data)
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

    @staticmethod
    def create_invited_user(
        db: Session,
        email: str,
        role: UserRole,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """
        Create a new user via Admin invitation (Flow 2).
        
        This is different from self-signup (Flow 1):
        - Flow 1: User signs up → Auth0 account created → Backend creates DB record
        - Flow 2: Admin invites → Auth0 account created → DB record created → Email sent
        
        This flow:
        1. Check if user exists
        2. Create user in Auth0 (triggers password setup email)
        3. Store user in local database
        4. User sets password via email link
        5. User logs in and backend links Auth0 account with DB record
        
        Args:
            db: Database session
            email: User's email address
            role: User's role
            first_name: User's first name (optional)
            last_name: User's last name (optional)
            
        Returns:
            User: Created user object
            
        Raises:
            Exception: If user already exists or creation fails
        """
        # Check if user already exists in local database
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise Exception(f"User with email {email} already exists in local database")
        
        # Create user in Auth0 (this also sends the password setup email)
        try:
            auth0_user = Auth0Management.create_user(
                email=email,
                role=role.value,
                first_name=first_name,
                last_name=last_name
            )
        except Exception as e:
            logger.error(f"Failed to create user in Auth0: {e}")
            raise
        
        # Extract Auth0 user ID
        auth0_id = auth0_user["user_id"]
        
        # Determine display name
        name_parts = []
        if first_name:
            name_parts.append(first_name)
        if last_name:
            name_parts.append(last_name)
        display_name = " ".join(name_parts) if name_parts else email
        
        # Create user in local database
        user_data = {
            'auth0_id': auth0_id,
            'email': email,
            'name': display_name,
            'first_name': first_name,
            'last_name': last_name,
            'email_verified': False,  # Will be verified after password setup
            'role': role,
            'is_active': True,
            'picture': auth0_user.get('picture')
        }
        
        user = User(**user_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"✅ Invited user created successfully: {email} with role {role.value}")
        
        return user
