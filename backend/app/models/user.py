"""
User model for PostgreSQL database.
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, Enum, ForeignKey, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from ..database import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    ADVISOR = "advisor"
    CLIENT = "client"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    FIRM_ADMIN = "firm_admin"
    FIRM_ADVISOR = "firm_advisor"


class UserRoleType(TypeDecorator):
    """Custom type that handles both enum and string values for user role.
    
    The database enum uses uppercase values (ADVISOR, CLIENT, etc.) but we want
    to use lowercase in Python. This type handles the conversion.
    """
    impl = String
    cache_ok = True
    
    def __init__(self, length=50):
        super().__init__(length)
    
    def process_bind_param(self, value, dialect):
        """Convert enum to database format when writing to database.
        
        Database enum has mixed case:
        - Old roles: ADVISOR, CLIENT, ADMIN, SUPER_ADMIN (uppercase)
        - New roles: firm_admin, firm_advisor (lowercase)
        """
        if value is None:
            return None
        if isinstance(value, UserRole):
            value_str = value.value
            # Map Python enum values to database enum values
            db_value_map = {
                'advisor': 'ADVISOR',
                'client': 'CLIENT',
                'admin': 'ADMIN',
                'super_admin': 'SUPER_ADMIN',
                'firm_admin': 'firm_admin',  # Keep lowercase (DB has it as lowercase)
                'firm_advisor': 'firm_advisor',  # Keep lowercase (DB has it as lowercase)
            }
            return db_value_map.get(value_str, value_str.upper())
        if isinstance(value, str):
            # If it's already a string, validate and convert
            value_lower = value.lower()
            db_value_map = {
                'advisor': 'ADVISOR',
                'client': 'CLIENT',
                'admin': 'ADMIN',
                'super_admin': 'SUPER_ADMIN',
                'firm_admin': 'firm_admin',
                'firm_advisor': 'firm_advisor',
            }
            if value_lower in db_value_map:
                return db_value_map[value_lower]
            # Validate it's a valid role value
            valid_values = [e.value for e in UserRole]
            if value_lower not in valid_values:
                raise ValueError(f"Invalid role: {value}. Must be one of {valid_values}")
            return value.upper()
        return str(value).upper()
    
    def process_result_value(self, value, dialect):
        """Convert database string to enum when reading from database."""
        if value is None:
            return None
        value_str = str(value)
        # Map uppercase database values to lowercase Python enum values
        lowercase_map = {
            'ADVISOR': 'advisor',
            'CLIENT': 'client',
            'ADMIN': 'admin',
            'SUPER_ADMIN': 'super_admin',
            'FIRM_ADMIN': 'firm_admin',  # Convert from uppercase DB value
            'FIRM_ADVISOR': 'firm_advisor',  # Convert from uppercase DB value
            # Also handle lowercase if they exist in DB
            'firm_admin': 'firm_admin',
            'firm_advisor': 'firm_advisor',
        }
        normalized = lowercase_map.get(value_str, value_str.lower())
        try:
            return UserRole(normalized)
        except ValueError:
            # If it's not a valid enum value, try to return as-is
            return value


class User(Base):
    """
    User model representing authenticated users in the system.
    
    This model stores user information from Auth0 and additional
    application-specific data.
    """
    __tablename__ = "users"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        comment="Unique identifier for the user"
    )
    
    # Auth0 Identity
    auth0_id = Column(
        String(255),
        unique=True,
        nullable=True,  # Allow NULL for users created with email/password
        index=True,
        comment="Auth0 user ID (sub claim from token). NULL for email/password users."
    )
    
    # Password (for email/password authentication)
    hashed_password = Column(
        String(255),
        nullable=True,
        comment="Hashed password for email/password authentication"
    )
    
    # Basic Information
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User's email address"
    )
    
    name = Column(
        String(255),
        nullable=True,
        comment="User's full name"
    )
    
    first_name = Column(
        String(255),
        nullable=True,
        comment="User's first name"
    )
    
    last_name = Column(
        String(255),
        nullable=True,
        comment="User's last name"
    )
    
    nickname = Column(
        String(255),
        nullable=True,
        comment="User's nickname"
    )
    
    picture = Column(
        Text,
        nullable=True,
        comment="URL to user's profile picture"
    )

    bio = Column(
        Text,
        nullable=True,
        comment="Short biography or profile description"
    )
    
    # Account Status
    email_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the email has been verified"
    )
    
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the user account is active"
    )
    
    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the user has been soft deleted"
    )
    
    # Role
    role = Column(
        UserRoleType(50),
        default=UserRole.ADVISOR,
        nullable=False,
        comment="User role (advisor, client, admin, super_admin, firm_admin, firm_advisor)"
    )
    
    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="When the user was created"
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="When the user was last updated"
    )
    
    last_login = Column(
        DateTime,
        nullable=True,
        comment="When the user last logged in"
    )
    
    # Firm relationship (for firm_admin and firm_advisor roles)
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Foreign key to firms table (for firm_admin and firm_advisor users)"
    )
    
    # Relationships
    firm = relationship("Firm", back_populates="advisors")
    media = relationship("Media", back_populates="user")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"
    
    def to_dict(self):
        """Convert user object to dictionary."""
        return {
            "id": str(self.id),
            "auth0_id": self.auth0_id,
            "email": self.email,
            "name": self.name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "nickname": self.nickname,
            "picture": self.picture,
            "bio": self.bio,
            "email_verified": self.email_verified,
            "is_active": self.is_active,
<<<<<<< HEAD
            "is_deleted": self.is_deleted,
            "role": self.role.value if self.role else None,
=======
            "role": self.role if self.role else None,
>>>>>>> c82ef43 (Enhance BBA Report Builder workflow and API integration)
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


