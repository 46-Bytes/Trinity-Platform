"""
Users API endpoints for user management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel

from ..database import get_db
from ..models.user import User, UserRole
from ..schemas.user import UserResponse
from ..utils.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    role: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    """
    List all users (admin/super_admin only).
    
    Args:
        role: Optional role filter (client, advisor, admin, etc.)
        skip: Number of records to skip
        limit: Maximum number of records to return
    """
    # Only admins and super_admins can list users
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view users"
        )
    
    query = db.query(User)
    
    # Filter by role if provided
    if role:
        try:
            role_enum = UserRole(role.lower())
            query = query.filter(User.role == role_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}"
            )
    
    users = query.offset(skip).limit(limit).all()
    # Convert users to response format with role as string
    return [
        UserResponse(
            id=u.id,
            auth0_id=u.auth0_id,
            email=u.email,
            name=u.name,
            given_name=u.given_name,
            family_name=u.family_name,
            nickname=u.nickname,
            picture=u.picture,
            email_verified=u.email_verified,
            is_active=u.is_active,
            role=u.role.value if hasattr(u.role, 'value') else str(u.role),
            created_at=u.created_at,
            updated_at=u.updated_at,
            last_login=u.last_login,
        )
        for u in users
    ]


class UserCreateRequest(BaseModel):
    """Request schema for creating a user."""
    email: str
    name: str
    role: str = "client"


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new user (admin/super_admin only).
    
    This endpoint allows admins to manually create users (typically clients)
    without requiring Auth0 authentication. 
    
    WORKFLOW:
    1. Admin creates user via this endpoint → User is created in database with placeholder auth0_id
    2. User signs up via Auth0 using the same email → Auth0 account is created
    3. Backend automatically links the accounts (matches by email) → User can now login
    
    NOTE: The user MUST signup via Auth0 (not login) to create their Auth0 account first.
    After signup, they can login normally. Login will fail if they haven't signed up yet.
    
    Args:
        email: User's email address
        name: User's full name
        role: User role (default: "client")
    """
    # Only admins and super_admins can create users
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create users"
        )
    
    # Validate role
    try:
        role_enum = UserRole(user_data.role.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {user_data.role}. Must be one of: client, advisor, admin, super_admin, firm_admin, firm_advisor"
        )
    
    # Check if user with this email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email {user_data.email} already exists"
        )
    
    # Generate a placeholder auth0_id for manual users
    # Format: "manual-{uuid}" - this indicates the user was created manually
    # The user will need to link their Auth0 account later
    manual_auth0_id = f"manual-{uuid4()}"
    
    # Split name into given_name and family_name if possible
    name_parts = user_data.name.split(" ", 1)
    given_name = name_parts[0] if name_parts else user_data.name
    family_name = name_parts[1] if len(name_parts) > 1 else None
    
    # Create new user
    new_user = User(
        auth0_id=manual_auth0_id,
        email=user_data.email,
        name=user_data.name,
        given_name=given_name,
        family_name=family_name,
        email_verified=False,  # Manual users need to verify email
        role=role_enum,
        is_active=True,
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        auth0_id=new_user.auth0_id,
        email=new_user.email,
        name=new_user.name,
        given_name=new_user.given_name,
        family_name=new_user.family_name,
        nickname=new_user.nickname,
        picture=new_user.picture,
        email_verified=new_user.email_verified,
        is_active=new_user.is_active,
        role=new_user.role.value if hasattr(new_user.role, 'value') else str(new_user.role),
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
        last_login=new_user.last_login,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific user by ID (admin/super_admin only).
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view user details"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    return UserResponse(
        id=user.id,
        auth0_id=user.auth0_id,
        email=user.email,
        name=user.name,
        given_name=user.given_name,
        family_name=user.family_name,
        nickname=user.nickname,
        picture=user.picture,
        email_verified=user.email_verified,
        is_active=user.is_active,
        role=user.role.value if hasattr(user.role, 'value') else str(user.role),
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    name: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a user (admin/super_admin only).
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update users"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    # Update fields if provided
    if name is not None:
        user.name = name
        # Update given_name and family_name
        name_parts = name.split(" ", 1)
        user.given_name = name_parts[0] if name_parts else name
        user.family_name = name_parts[1] if len(name_parts) > 1 else None
    
    if role is not None:
        try:
            role_enum = UserRole(role.lower())
            user.role = role_enum
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}"
            )
    
    if is_active is not None:
        user.is_active = is_active
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        auth0_id=user.auth0_id,
        email=user.email,
        name=user.name,
        given_name=user.given_name,
        family_name=user.family_name,
        nickname=user.nickname,
        picture=user.picture,
        email_verified=user.email_verified,
        is_active=user.is_active,
        role=user.role.value if hasattr(user.role, 'value') else str(user.role),
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
    )

