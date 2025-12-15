"""
User model for PostgreSQL database.
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, Enum
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
        nullable=False,
        index=True,
        comment="Auth0 user ID (sub claim from token)"
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
    
    given_name = Column(
        String(255),
        nullable=True,
        comment="User's first/given name"
    )
    
    family_name = Column(
        String(255),
        nullable=True,
        comment="User's last/family name"
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
    
    # Role
    role = Column(
        Enum(UserRole),
        default=UserRole.ADVISOR,
        nullable=False,
        comment="User role (advisor, client, admin, super_admin)"
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
    
    # Relationships
    media = relationship("Media", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.email}>"
    
    def to_dict(self):
        """Convert user object to dictionary."""
        return {
            "id": str(self.id),
            "auth0_id": self.auth0_id,
            "email": self.email,
            "name": self.name,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "nickname": self.nickname,
            "picture": self.picture,
            "email_verified": self.email_verified,
            "is_active": self.is_active,
            "role": self.role.value if self.role else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


