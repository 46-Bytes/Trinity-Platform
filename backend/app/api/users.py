"""
Users API endpoints for user management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel

from ..database import get_db
from ..models.user import User, UserRole
from ..schemas.user import UserResponse, UserUpdate
from ..utils.auth import get_current_user
from ..services.auth_service import AuthService

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    role: Optional[str] = None,
    ids: Optional[str] = Query(None, description="Comma-separated list of user IDs to filter by"),
    skip: int = 0,
    limit: int = 100,
):
    """
    List all users (admin/super_admin only).
    
    Args:
        role: Optional role filter (client, advisor, admin, etc.)
        ids: Optional comma-separated list of user IDs to filter by
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
    
    # Track if we're filtering by specific IDs (for superadmin viewing firm clients)
    filtering_by_ids = False
    
    # Filter by IDs if provided
    if ids:
        try:
            # Parse comma-separated IDs
            id_list = [UUID(id_str.strip()) for id_str in ids.split(',') if id_str.strip()]
            if id_list:
                query = query.filter(User.id.in_(id_list))
                filtering_by_ids = True
            else:
                # If no valid IDs, return empty result
                return []
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user IDs format. Expected comma-separated UUIDs."
            )
    
    # Filter by role if provided
    if role:
        try:
            role_enum = UserRole(role.lower())
            query = query.filter(User.role == role_enum)

            if role_enum == UserRole.CLIENT and current_user.role == UserRole.ADMIN and not filtering_by_ids:
                query = query.filter(User.firm_id.is_(None))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f"Invalid role: {role}")
    elif current_user.role == UserRole.ADMIN and not filtering_by_ids:

        query = query.filter(User.firm_id.is_(None))
    
    users = query.offset(skip).limit(limit).all()
    # Convert users to response format with role as string
    return [
        UserResponse(
            id=u.id,
            auth0_id=u.auth0_id,
            email=u.email,
            name=u.name,
            first_name=u.first_name,
            last_name=u.last_name,
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
    Create a new user via Admin invitation (admin/super_admin only).
    
    This is FLOW 2: Admin-Invited Users
    
    WORKFLOW:
    1. Admin creates user → Stored in local DB + Auth0
    2. Auth0 automatically sends "Set Password" email to user
    3. User clicks email link → Auth0's password setup page
    4. User sets password + username → Email marked as verified
    5. User auto-redirected to login page
    6. User logs in → Backend links Auth0 account with local DB record
    
    This is different from FLOW 1 (Self-Signup):
    - Advisors can still sign up on their own via Auth0 Universal Login
    - That flow creates Auth0 account first, then DB record
    
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
    
    # Check if user with this email already exists in local DB
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email {user_data.email} already exists"
        )
    
    # Split name into first_name and last_name
    name_parts = user_data.name.split(" ", 1)
    first_name = name_parts[0] if name_parts else user_data.name
    last_name = name_parts[1] if len(name_parts) > 1 else None
    
    try:
        # Create invited user (Flow 2)
        new_user = AuthService.create_invited_user(
            db=db,
            email=user_data.email,
            role=role_enum,
            first_name=first_name,
            last_name=last_name
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return UserResponse(
        id=new_user.id,
        auth0_id=new_user.auth0_id,
        email=new_user.email,
        name=new_user.name,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
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
        first_name=user.first_name,
        last_name=user.last_name,
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
    user_update: UserUpdate,
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
    if user_update.name is not None:
        user.name = user_update.name
        # Update first_name and last_name
        name_parts = user_update.name.split(" ", 1)
        user.first_name = name_parts[0] if name_parts else user_update.name
        user.last_name = name_parts[1] if len(name_parts) > 1 else None
    
    if user_update.role is not None:
        try:
            role_enum = UserRole(user_update.role.lower())
            user.role = role_enum
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {user_update.role}"
            )
    
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        auth0_id=user.auth0_id,
        email=user.email,
        name=user.name,
        first_name=user.first_name,
        last_name=user.last_name,
        nickname=user.nickname,
        picture=user.picture,
        email_verified=user.email_verified,
        is_active=user.is_active,
        role=user.role.value if hasattr(user.role, 'value') else str(user.role),
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
    )

