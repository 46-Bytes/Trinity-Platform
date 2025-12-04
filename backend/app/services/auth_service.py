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
    def extract_role_from_auth0(user_info: dict) -> UserRole:
        """
        Extract user role from Auth0 user info.
        
        Checks in order:
        1. app_metadata.role
        2. user_metadata.role
        3. Default to ADVISOR
        
        Args:
            user_info: User information from Auth0
            
        Returns:
            UserRole: User role
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
        
        # Default to advisor
        return UserRole.ADVISOR
    
    @staticmethod
    def get_or_create_user(db: Session, user_info: dict) -> User:
        """
        Get existing user or create new user from Auth0 user info.
        
        Args:
            db: Database session
            user_info: User information from Auth0
            
        Returns:
            User: User object
        """
        auth0_id = user_info.get('sub')
        email = user_info.get('email')
        
        # Extract role from Auth0
        role = AuthService.extract_role_from_auth0(user_info)
        
        # Try to find existing user
        user = db.query(User).filter(User.auth0_id == auth0_id).first()
        
        if user:
            # Update existing user information
            user.email = email
            user.name = user_info.get('name')
            user.given_name = user_info.get('given_name')
            user.family_name = user_info.get('family_name')
            user.nickname = user_info.get('nickname')
            user.picture = user_info.get('picture')
            
            # IMPORTANT: Only update email_verified if it's True (don't unverify)
            # If user already has verified email, keep it verified
            # Only update if Auth0 says it's verified (prevents unverifying)
            auth0_email_verified = user_info.get('email_verified', False)
            if auth0_email_verified:
                user.email_verified = True  # Update to verified
            # If False, don't change existing verified status (preserve verified state)
            
            user.role = role  # Update role from Auth0
            user.last_login = datetime.utcnow()
            user.updated_at = datetime.utcnow()
        else:
            # Create new user
            user = User(
                auth0_id=auth0_id,
                email=email,
                name=user_info.get('name'),
                given_name=user_info.get('given_name'),
                family_name=user_info.get('family_name'),
                nickname=user_info.get('nickname'),
                picture=user_info.get('picture'),
                email_verified=user_info.get('email_verified', False),
                role=role,  # Set role from Auth0
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


