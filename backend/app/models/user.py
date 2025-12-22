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


class NormalizedUserRoleEnum(TypeDecorator):
    """
    Custom TypeDecorator that normalizes enum values when reading from database.
    
    This handles the case where PostgreSQL stores uppercase enum values (ADMIN, CLIENT, etc.)
    but the Python enum uses lowercase values (admin, client, etc.).
    
    Uses Enum as the underlying type with all possible database values.
    """
    impl = Enum
    cache_ok = True
    
    # Map uppercase to lowercase for normalization (reading)
    _normalize_map = {
        'ADVISOR': 'advisor',
        'CLIENT': 'client',
        'ADMIN': 'admin',
        'SUPER_ADMIN': 'super_admin',
        'FIRM_ADMIN': 'firm_admin',
        'FIRM_ADVISOR': 'firm_advisor',
    }
    
    # Map lowercase to database format (writing)
    _db_value_map = {
        'advisor': 'ADVISOR',
        'client': 'CLIENT',
        'admin': 'ADMIN',
        'super_admin': 'SUPER_ADMIN',
        'firm_admin': 'firm_admin',  # Already lowercase in DB
        'firm_advisor': 'firm_advisor',  # Already lowercase in DB
    }
    
    def __init__(self, enum_class, *args, **kwargs):
        self.enum_class = enum_class
        # Create Enum with all possible database values (both uppercase and lowercase)
        # This allows SQLAlchemy to accept both formats
        db_enum_values = ['ADVISOR', 'CLIENT', 'ADMIN', 'SUPER_ADMIN', 'firm_admin', 'firm_advisor']
        # Remove native_enum and create_type from kwargs to avoid conflicts
        kwargs.pop('native_enum', None)
        kwargs.pop('create_type', None)
        super().__init__(*db_enum_values, name='userrole', native_enum=True, create_type=False, *args, **kwargs)
    
    def process_bind_param(self, value, dialect):
        """Convert enum to database format when writing."""
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            enum_value = value.value
        else:
            enum_value = str(value)
        
        # Convert to database format (uppercase for old roles, lowercase for new)
        db_value = self._db_value_map.get(enum_value, enum_value.upper())
        
        # Return the value - the underlying Enum will handle it
        return db_value
    
    def process_result_value(self, value, dialect):
        """Normalize enum value when reading from database."""
        if value is None:
            return None
        
        # If value is already an enum, return as-is
        if isinstance(value, self.enum_class):
            return value
        
        # If value is a string, normalize it
        if isinstance(value, str):
            # Check if it's uppercase and needs normalization
            normalized = self._normalize_map.get(value, value.lower())
            try:
                return self.enum_class(normalized)
            except ValueError:
                # If normalization fails, try case-insensitive lookup
                for enum_member in self.enum_class:
                    if enum_member.value.lower() == value.lower():
                        return enum_member
                # If still not found, raise error
                raise ValueError(f"Invalid enum value: {value}. Expected one of: {[e.value for e in self.enum_class]}")
        
        # Try to convert directly
        try:
            return self.enum_class(value)
        except (ValueError, TypeError):
            # Try normalization as last resort
            if isinstance(value, str):
                normalized = self._normalize_map.get(value.upper(), value.lower())
                return self.enum_class(normalized)
            raise ValueError(f"Cannot convert {value} to {self.enum_class}")


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
    
    # Role
    role = Column(
        NormalizedUserRoleEnum(UserRole, values_callable=lambda x: [e.value for e in x], native_enum=True, create_type=False),
        default=UserRole.ADVISOR,
        nullable=False,
        comment="User role (advisor, client, admin, super_admin, firm_admin, firm_advisor)"
    )
    
    # Firm Relationship (for firm advisors and firm admin)
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Foreign key to firms (NULL for solo advisors/clients)"
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
    firm = relationship("Firm", back_populates="advisors")
    
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
            "bio": self.bio,
            "email_verified": self.email_verified,
            "is_active": self.is_active,
            "role": self.role.value if self.role else None,
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


