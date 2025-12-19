# Firm Account & Multi-Advisor Support - Implementation Guide

## Overview
This document outlines the complete implementation strategy for adding Firm Account functionality to Trinity Platform, enabling multi-advisor practices with centralized management.

---

## 1. Database Schema Changes

### 1.1 Create Firm Model

**File: `backend/app/models/firm.py`**

```python
"""
Firm model for multi-advisor organizations.
"""
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from ..database import Base


class Firm(Base):
    """
    Firm represents an organization that employs multiple advisors.
    Each firm has one Firm Admin who manages billing and users.
    """
    __tablename__ = "firms"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        comment="Unique identifier for the firm"
    )
    
    # Firm Information
    firm_name = Column(
        String(255),
        nullable=False,
        comment="Name of the firm/organization"
    )
    
    # Firm Admin (the primary user who manages the firm)
    firm_admin_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        comment="Foreign key to users (the Firm Admin)"
    )
    
    # Subscription & Billing
    subscription_plan = Column(
        String(50),
        nullable=True,
        comment="Subscription plan name (e.g., 'professional', 'enterprise')"
    )
    
    seat_count = Column(
        Integer,
        nullable=False,
        default=5,
        comment="Number of seats purchased (minimum 5)"
    )
    
    seats_used = Column(
        Integer,
        nullable=False,
        default=1,  # At least the Firm Admin
        comment="Number of active advisor seats in use"
    )
    
    billing_email = Column(
        String(255),
        nullable=True,
        comment="Email for billing notifications"
    )
    
    # Status
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the firm account is active"
    )
    
    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="When the firm was created"
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="When the firm was last updated"
    )
    
    # Relationships
    advisors = relationship("User", back_populates="firm", foreign_keys="User.firm_id")
    engagements = relationship("Engagement", back_populates="firm")
    
    def __repr__(self):
        return f"<Firm {self.firm_name}>"
```

### 1.2 Update User Model

**File: `backend/app/models/user.py`**

Add to `UserRole` enum:
```python
class UserRole(str, enum.Enum):
    """User role enumeration."""
    ADVISOR = "advisor"
    CLIENT = "client"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    FIRM_ADMIN = "firm_admin"      # NEW
    FIRM_ADVISOR = "firm_advisor"  # NEW
```

Add to `User` model:
```python
# Firm Relationship (for firm advisors and firm admin)
firm_id = Column(
    UUID(as_uuid=True),
    nullable=True,
    index=True,
    comment="Foreign key to firms (NULL for solo advisors/clients)"
)

# Relationship
firm = relationship("Firm", back_populates="advisors", foreign_keys=[firm_id])
```

### 1.3 Update Engagement Model

The Engagement model already has:
- `firm_id` ✅ (already exists)
- `primary_advisor_id` ✅ (already exists)
- `secondary_advisor_ids` ✅ (already exists)

Just need to add relationship:
```python
firm = relationship("Firm", back_populates="engagements")
```

### 1.4 Create Subscription Model (Optional - for billing tracking)

**File: `backend/app/models/subscription.py`**

```python
"""
Subscription model for tracking firm billing.
"""
from sqlalchemy import Column, String, DateTime, Integer, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from ..database import Base


class Subscription(Base):
    """
    Tracks firm subscription and billing information.
    """
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    
    plan_name = Column(String(50), nullable=False)
    seat_count = Column(Integer, nullable=False)
    monthly_price = Column(Numeric(10, 2), nullable=False)
    
    status = Column(String(20), nullable=False, default="active")  # active, cancelled, past_due
    
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    
    stripe_subscription_id = Column(String(255), nullable=True)  # If using Stripe
    stripe_customer_id = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

---

## 2. Permission & Access Control Logic

### 2.1 Update Role Check Service

**File: `backend/app/services/role_check.py`**

Update `check_engagement_access()`:

```python
def check_engagement_access(
    engagement,
    user: User,
    require_advisor: bool = False
) -> bool:
    """
    Check if user has access to an engagement.
    
    Rules:
    - Super Admin: Access to all
    - Admin: Access to all
    - Firm Admin: Access to all engagements in their firm
    - Firm Advisor: Access if assigned to engagement AND in same firm
    - Advisor (solo): Access if assigned to engagement
    - Client: Access if they are client_id
    
    Args:
        engagement: Engagement to check
        user: Current user
        require_advisor: If True, only advisors can access
        
    Returns:
        bool: True if user has access
    """
    # Super Admin and Admin have full access
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True
    
    # Firm Admin: Access to all engagements in their firm
    if user.role == UserRole.FIRM_ADMIN:
        if engagement.firm_id and engagement.firm_id == user.firm_id:
            return True
        return False
    
    # Firm Advisor: Access if assigned AND in same firm
    if user.role == UserRole.FIRM_ADVISOR:
        if require_advisor and engagement.firm_id != user.firm_id:
            return False
        if engagement.firm_id == user.firm_id:
            # Check if assigned as primary or secondary advisor
            if engagement.primary_advisor_id == user.id:
                return True
            if engagement.secondary_advisor_ids and user.id in engagement.secondary_advisor_ids:
                return True
        return False
    
    # Solo Advisor access
    if user.role == UserRole.ADVISOR:
        if engagement.primary_advisor_id == user.id:
            return True
        if engagement.secondary_advisor_ids and user.id in engagement.secondary_advisor_ids:
            return True
        return False
    
    # Client access
    if user.role == UserRole.CLIENT:
        if require_advisor:
            return False
        return engagement.client_id == user.id
    
    return False
```

### 2.2 Create Firm Permission Helper

**File: `backend/app/services/firm_permissions.py`**

```python
"""
Firm-specific permission checks.
"""
from sqlalchemy.orm import Session
from ..models.user import User, UserRole
from ..models.firm import Firm
from uuid import UUID


def is_firm_admin(user: User) -> bool:
    """Check if user is a Firm Admin."""
    return user.role == UserRole.FIRM_ADMIN


def is_firm_advisor(user: User) -> bool:
    """Check if user is a Firm Advisor."""
    return user.role == UserRole.FIRM_ADVISOR


def is_firm_member(user: User) -> bool:
    """Check if user belongs to a firm."""
    return user.role in [UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR] and user.firm_id is not None


def can_manage_firm_users(user: User, firm_id: UUID) -> bool:
    """Check if user can manage users in a firm."""
    if user.role == UserRole.SUPER_ADMIN:
        return True
    if is_firm_admin(user) and user.firm_id == firm_id:
        return True
    return False


def can_view_firm_engagements(user: User, firm_id: UUID) -> bool:
    """Check if user can view all engagements in a firm."""
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True
    if is_firm_admin(user) and user.firm_id == firm_id:
        return True
    return False


def can_assign_advisors(user: User, firm_id: UUID) -> bool:
    """Check if user can assign advisors to engagements."""
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True
    if is_firm_admin(user) and user.firm_id == firm_id:
        return True
    return False
```

---

## 3. Service Layer

### 3.1 Create Firm Service

**File: `backend/app/services/firm_service.py`**

```python
"""
Firm service for managing firm accounts and advisors.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from ..models.firm import Firm
from ..models.user import User, UserRole
from ..models.engagement import Engagement
from ..services.firm_permissions import can_manage_firm_users, can_view_firm_engagements


class FirmService:
    """Service for managing firm accounts."""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    def create_firm(
        self,
        firm_name: str,
        firm_admin_id: UUID,
        seat_count: int = 5
    ) -> Firm:
        """
        Create a new firm account.
        
        Args:
            firm_name: Name of the firm
            firm_admin_id: User ID of the Firm Admin
            seat_count: Number of seats (minimum 5)
            
        Returns:
            Created Firm model
        """
        # Verify firm admin exists and is not already in a firm
        firm_admin = self.db.query(User).filter(User.id == firm_admin_id).first()
        if not firm_admin:
            raise ValueError(f"User {firm_admin_id} not found")
        
        if firm_admin.firm_id:
            raise ValueError("User is already part of a firm")
        
        if seat_count < 5:
            raise ValueError("Minimum seat count is 5")
        
        # Create firm
        firm = Firm(
            firm_name=firm_name,
            firm_admin_id=firm_admin_id,
            seat_count=seat_count,
            seats_used=1  # Just the Firm Admin
        )
        
        self.db.add(firm)
        self.db.flush()  # Get firm.id
        
        # Update firm admin
        firm_admin.firm_id = firm.id
        firm_admin.role = UserRole.FIRM_ADMIN
        
        self.db.commit()
        self.db.refresh(firm)
        
        self.logger.info(f"Firm created: {firm.id} by {firm_admin_id}")
        return firm
    
    def add_advisor_to_firm(
        self,
        firm_id: UUID,
        advisor_email: str,
        advisor_name: str,
        added_by_user_id: UUID
    ) -> User:
        """
        Add an advisor to a firm.
        
        Args:
            firm_id: Firm ID
            advisor_email: Email of advisor to add
            advisor_name: Name of advisor
            added_by_user_id: User ID of person adding (must be Firm Admin)
            
        Returns:
            Created or updated User model
        """
        # Check permissions
        added_by = self.db.query(User).filter(User.id == added_by_user_id).first()
        if not can_manage_firm_users(added_by, firm_id):
            raise ValueError("Only Firm Admins can add advisors")
        
        firm = self.db.query(Firm).filter(Firm.id == firm_id).first()
        if not firm:
            raise ValueError(f"Firm {firm_id} not found")
        
        # Check seat availability
        if firm.seats_used >= firm.seat_count:
            raise ValueError(f"Firm has reached seat limit ({firm.seat_count})")
        
        # Check if user already exists
        advisor = self.db.query(User).filter(User.email == advisor_email).first()
        
        if advisor:
            if advisor.firm_id:
                raise ValueError("User is already part of a firm")
            # Update existing user
            advisor.firm_id = firm_id
            advisor.role = UserRole.FIRM_ADVISOR
            advisor.name = advisor_name or advisor.name
        else:
            # Create new user (will need Auth0 setup separately)
            advisor = User(
                auth0_id=f"firm_{firm_id}_{advisor_email}",  # Placeholder - needs real Auth0 ID
                email=advisor_email,
                name=advisor_name,
                role=UserRole.FIRM_ADVISOR,
                firm_id=firm_id,
                is_active=True
            )
            self.db.add(advisor)
        
        firm.seats_used += 1
        self.db.commit()
        self.db.refresh(advisor)
        
        self.logger.info(f"Advisor {advisor.id} added to firm {firm_id}")
        return advisor
    
    def remove_advisor_from_firm(
        self,
        firm_id: UUID,
        advisor_id: UUID,
        removed_by_user_id: UUID
    ) -> None:
        """
        Remove an advisor from a firm.
        
        This immediately revokes access to all engagements.
        """
        # Check permissions
        removed_by = self.db.query(User).filter(User.id == removed_by_user_id).first()
        if not can_manage_firm_users(removed_by, firm_id):
            raise ValueError("Only Firm Admins can remove advisors")
        
        firm = self.db.query(Firm).filter(Firm.id == firm_id).first()
        advisor = self.db.query(User).filter(User.id == advisor_id).first()
        
        if not advisor or advisor.firm_id != firm_id:
            raise ValueError("Advisor not found in firm")
        
        if advisor.role == UserRole.FIRM_ADMIN:
            raise ValueError("Cannot remove Firm Admin")
        
        # Remove from all engagements
        # Remove as primary advisor (reassign to Firm Admin)
        engagements_as_primary = self.db.query(Engagement).filter(
            Engagement.primary_advisor_id == advisor_id,
            Engagement.firm_id == firm_id
        ).all()
        
        for engagement in engagements_as_primary:
            engagement.primary_advisor_id = firm.firm_admin_id
        
        # Remove from secondary advisors
        engagements_as_secondary = self.db.query(Engagement).filter(
            Engagement.firm_id == firm_id
        ).all()
        
        for engagement in engagements_as_secondary:
            if engagement.secondary_advisor_ids and advisor_id in engagement.secondary_advisor_ids:
                engagement.secondary_advisor_ids = [
                    aid for aid in engagement.secondary_advisor_ids if aid != advisor_id
                ]
        
        # Remove advisor
        advisor.firm_id = None
        advisor.role = UserRole.ADVISOR  # Revert to solo advisor
        advisor.is_active = False  # Deactivate account
        
        firm.seats_used -= 1
        self.db.commit()
        
        self.logger.info(f"Advisor {advisor_id} removed from firm {firm_id}")
    
    def get_firm_advisors(self, firm_id: UUID, current_user: User) -> List[User]:
        """Get all advisors in a firm."""
        if not can_view_firm_engagements(current_user, firm_id):
            raise ValueError("Insufficient permissions")
        
        return self.db.query(User).filter(
            User.firm_id == firm_id,
            User.role.in_([UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR])
        ).all()
    
    def get_firm_engagements(self, firm_id: UUID, current_user: User) -> List[Engagement]:
        """Get all engagements for a firm."""
        if not can_view_firm_engagements(current_user, firm_id):
            raise ValueError("Insufficient permissions")
        
        return self.db.query(Engagement).filter(
            Engagement.firm_id == firm_id
        ).order_by(Engagement.created_at.desc()).all()
    
    def update_seat_count(self, firm_id: UUID, new_seat_count: int, updated_by: UUID) -> Firm:
        """Update firm seat count (triggers billing update)."""
        firm = self.db.query(Firm).filter(Firm.id == firm_id).first()
        if not firm:
            raise ValueError("Firm not found")
        
        # Check permissions
        updater = self.db.query(User).filter(User.id == updated_by).first()
        if not can_manage_firm_users(updater, firm_id):
            raise ValueError("Only Firm Admins can update seat count")
        
        if new_seat_count < firm.seats_used:
            raise ValueError(f"Cannot reduce seats below current usage ({firm.seats_used})")
        
        if new_seat_count < 5:
            raise ValueError("Minimum seat count is 5")
        
        firm.seat_count = new_seat_count
        self.db.commit()
        self.db.refresh(firm)
        
        # TODO: Trigger billing update webhook/API call
        
        return firm


def get_firm_service(db: Session) -> FirmService:
    """Factory function to create FirmService."""
    return FirmService(db)
```

---

## 4. API Endpoints

### 4.1 Update Engagements API

**File: `backend/app/api/engagements.py`**

Update `list_engagements()` to handle firm roles:

```python
@router.get("", response_model=List[EngagementListItem])
async def list_engagements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
    status_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    List engagements accessible to the current user.
    
    Returns engagements based on user role:
    - Super Admin/Admin: All engagements
    - Firm Admin: All engagements in their firm
    - Firm Advisor: Engagements where they are assigned (in their firm)
    - Advisor (solo): Engagements where they are primary or secondary advisor
    - Client: Engagements where they are the client
    """
    query = db.query(Engagement)
    
    # Apply role-based filtering
    if current_user.role == UserRole.SUPER_ADMIN or current_user.role == UserRole.ADMIN:
        # Admins see all
        pass
    elif current_user.role == UserRole.FIRM_ADMIN:
        # Firm Admin sees all engagements in their firm
        query = query.filter(Engagement.firm_id == current_user.firm_id)
    elif current_user.role == UserRole.FIRM_ADVISOR:
        # Firm Advisor sees engagements where they are involved (in their firm)
        query = query.filter(
            Engagement.firm_id == current_user.firm_id
        ).filter(
            or_(
                Engagement.primary_advisor_id == current_user.id,
                text("secondary_advisor_ids @> ARRAY[:user_id]::uuid[]").bindparams(user_id=current_user.id)
            )
        )
    elif current_user.role == UserRole.ADVISOR:
        # Solo advisors see engagements where they are involved
        query = query.filter(
            or_(
                Engagement.primary_advisor_id == current_user.id,
                text("secondary_advisor_ids @> ARRAY[:user_id]::uuid[]").bindparams(user_id=current_user.id)
            )
        )
    elif current_user.role == UserRole.CLIENT:
        # Clients see only their engagements
        query = query.filter(Engagement.client_id == current_user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user role."
        )
    
    # ... rest of the function remains the same
```

### 4.2 Create Firm API

**File: `backend/app/api/firms.py`**

```python
"""
Firm management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ..database import get_db
from ..models.user import User
from ..services.role_check import get_current_user_from_token
from ..services.firm_service import get_firm_service, FirmService
from ..schemas.firm import (
    FirmCreate,
    FirmResponse,
    FirmAdvisorAdd,
    FirmAdvisorResponse,
    FirmEngagementResponse
)

router = APIRouter(prefix="/api/firms", tags=["firms"])


@router.post("", response_model=FirmResponse, status_code=status.HTTP_201_CREATED)
async def create_firm(
    firm_data: FirmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Create a new firm account."""
    # Only allow Super Admin or existing advisors to create firms
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADVISOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors can create firm accounts"
        )
    
    firm_service = get_firm_service(db)
    firm = firm_service.create_firm(
        firm_name=firm_data.firm_name,
        firm_admin_id=current_user.id,
        seat_count=firm_data.seat_count or 5
    )
    
    return FirmResponse.model_validate(firm)


@router.get("/{firm_id}", response_model=FirmResponse)
async def get_firm(
    firm_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Get firm details."""
    from ..models.firm import Firm
    firm = db.query(Firm).filter(Firm.id == firm_id).first()
    
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")
    
    # Check access
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        if current_user.firm_id != firm_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return FirmResponse.model_validate(firm)


@router.post("/{firm_id}/advisors", response_model=FirmAdvisorResponse)
async def add_advisor(
    firm_id: UUID,
    advisor_data: FirmAdvisorAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Add an advisor to a firm."""
    firm_service = get_firm_service(db)
    advisor = firm_service.add_advisor_to_firm(
        firm_id=firm_id,
        advisor_email=advisor_data.email,
        advisor_name=advisor_data.name,
        added_by_user_id=current_user.id
    )
    
    return FirmAdvisorResponse.model_validate(advisor)


@router.delete("/{firm_id}/advisors/{advisor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_advisor(
    firm_id: UUID,
    advisor_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Remove an advisor from a firm."""
    firm_service = get_firm_service(db)
    firm_service.remove_advisor_from_firm(
        firm_id=firm_id,
        advisor_id=advisor_id,
        removed_by_user_id=current_user.id
    )
    
    return None


@router.get("/{firm_id}/advisors", response_model=List[FirmAdvisorResponse])
async def list_advisors(
    firm_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """List all advisors in a firm."""
    firm_service = get_firm_service(db)
    advisors = firm_service.get_firm_advisors(firm_id, current_user)
    
    return [FirmAdvisorResponse.model_validate(a) for a in advisors]


@router.get("/{firm_id}/engagements", response_model=List[FirmEngagementResponse])
async def list_firm_engagements(
    firm_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """List all engagements for a firm."""
    firm_service = get_firm_service(db)
    engagements = firm_service.get_firm_engagements(firm_id, current_user)
    
    return [FirmEngagementResponse.model_validate(e) for e in engagements]


@router.patch("/{firm_id}/seats", response_model=FirmResponse)
async def update_seats(
    firm_id: UUID,
    seat_count: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """Update firm seat count."""
    firm_service = get_firm_service(db)
    firm = firm_service.update_seat_count(firm_id, seat_count, current_user.id)
    
    return FirmResponse.model_validate(firm)
```

---

## 5. Schema Definitions

**File: `backend/app/schemas/firm.py`**

```python
"""
Firm schemas for API requests/responses.
"""
from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class FirmCreate(BaseModel):
    firm_name: str
    seat_count: Optional[int] = 5


class FirmResponse(BaseModel):
    id: UUID
    firm_name: str
    firm_admin_id: UUID
    subscription_plan: Optional[str]
    seat_count: int
    seats_used: int
    billing_email: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FirmAdvisorAdd(BaseModel):
    email: EmailStr
    name: str


class FirmAdvisorResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str]
    role: str
    is_active: bool
    firm_id: UUID
    
    class Config:
        from_attributes = True


class FirmEngagementResponse(BaseModel):
    id: UUID
    engagement_name: str
    business_name: Optional[str]
    client_id: UUID
    primary_advisor_id: UUID
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True
```

---

## 6. Task Filtering Updates

**File: `backend/app/api/tasks.py`**

Update task listing to respect firm boundaries:

```python
@router.get("")
async def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
    # ... filters
):
    query = db.query(Task)
    
    # Firm Admin: See all tasks in firm engagements
    if current_user.role == UserRole.FIRM_ADMIN:
        firm_engagement_ids = db.query(Engagement.id).filter(
            Engagement.firm_id == current_user.firm_id
        ).subquery()
        query = query.filter(Task.engagement_id.in_(select(firm_engagement_ids)))
    
    # Firm Advisor: See tasks in assigned engagements only
    elif current_user.role == UserRole.FIRM_ADVISOR:
        assigned_engagement_ids = db.query(Engagement.id).filter(
            Engagement.firm_id == current_user.firm_id
        ).filter(
            or_(
                Engagement.primary_advisor_id == current_user.id,
                text("secondary_advisor_ids @> ARRAY[:user_id]::uuid[]").bindparams(user_id=current_user.id)
            )
        ).subquery()
        query = query.filter(Task.engagement_id.in_(select(assigned_engagement_ids)))
    
    # ... rest of filtering logic
```

---

## 7. Migration Strategy

### 7.1 Database Migration

**File: `backend/alembic/versions/XXXX_add_firm_support.py`**

```python
"""Add firm support

Revision ID: xxxx
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create firms table
    op.create_table(
        'firms',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_name', sa.String(255), nullable=False),
        sa.Column('firm_admin_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('subscription_plan', sa.String(50), nullable=True),
        sa.Column('seat_count', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('seats_used', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('billing_email', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    
    # Add firm_id to users
    op.add_column('users', sa.Column('firm_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_users_firm_id', 'users', ['firm_id'])
    
    # Update UserRole enum to include FIRM_ADMIN and FIRM_ADVISOR
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'firm_admin'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'firm_advisor'")
    
    # engagements.firm_id already exists, just ensure it's indexed
    op.create_index('ix_engagements_firm_id', 'engagements', ['firm_id'], if_not_exists=True)
```

### 7.2 Migrate Existing Advisors (Optional)

Create a script to convert existing solo advisors to firm accounts:

```python
# backend/scripts/migrate_to_firm.py
"""
Migration script to convert solo advisors to firm accounts.
"""
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.firm import Firm
from app.services.firm_service import FirmService

def migrate_solo_advisor_to_firm(advisor_id: UUID, firm_name: str):
    """Convert a solo advisor into a Firm Admin of a new firm."""
    db = SessionLocal()
    try:
        advisor = db.query(User).filter(User.id == advisor_id).first()
        if not advisor or advisor.role != UserRole.ADVISOR:
            raise ValueError("User is not a solo advisor")
        
        firm_service = FirmService(db)
        firm = firm_service.create_firm(
            firm_name=firm_name,
            firm_admin_id=advisor_id,
            seat_count=5
        )
        
        print(f"✅ Created firm {firm.id} for advisor {advisor_id}")
        return firm
    finally:
        db.close()
```

---

## 8. Frontend Updates

### 8.1 Update Auth Service

**File: `frontend/src/services/authService.ts`**

Ensure `firm_admin` and `firm_advisor` roles are handled.

### 8.2 Create Firm Management Page

**File: `frontend/src/pages/dashboard/firm/FirmManagementPage.tsx`**

Create UI for:
- Viewing firm details
- Managing advisors (add/remove)
- Viewing seat usage
- Managing billing
- Viewing all firm engagements
- Reassigning engagements

### 8.3 Update Engagement Filters

Update engagement listing to show firm context for Firm Admins.

---

## 9. Key Implementation Points

### 9.1 Permission Matrix

| Action | Super Admin | Admin | Firm Admin | Firm Advisor | Solo Advisor | Client |
|--------|-------------|-------|------------|--------------|--------------|--------|
| View all firm engagements | ✅ | ✅ | ✅ (own firm) | ❌ | ❌ | ❌ |
| View assigned engagements | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (own) |
| Add advisors to firm | ✅ | ✅ | ✅ (own firm) | ❌ | ❌ | ❌ |
| Remove advisors | ✅ | ✅ | ✅ (own firm) | ❌ | ❌ | ❌ |
| Assign advisors to engagement | ✅ | ✅ | ✅ (own firm) | ❌ | ✅ (own) | ❌ |
| Reassign engagements | ✅ | ✅ | ✅ (own firm) | ❌ | ❌ | ❌ |
| Manage billing | ✅ | ✅ | ✅ (own firm) | ❌ | ❌ | ❌ |

### 9.2 Data Ownership

- **Engagements belong to the firm**, not individual advisors
- When an advisor is removed, engagements are reassigned to Firm Admin
- All documents, diagnostics, and tasks remain with the firm
- Clients are shared across the firm (Firm Admin can see all)

### 9.3 Billing Integration

- Seat count changes trigger billing updates
- Minimum 5 seats enforced
- Billing email stored on Firm model
- Integration with Stripe/other payment provider needed

---

## 10. Testing Checklist

- [ ] Create firm account
- [ ] Add advisors to firm
- [ ] Remove advisors (verify engagement reassignment)
- [ ] Firm Admin views all firm engagements
- [ ] Firm Advisor only sees assigned engagements
- [ ] Update seat count
- [ ] Create engagement with firm_id
- [ ] Assign advisors to engagement
- [ ] Task filtering respects firm boundaries
- [ ] Permission checks for all endpoints
- [ ] Migration script for existing advisors

---

## Summary

This implementation adds firm account support while maintaining backward compatibility with solo advisors. The key changes are:

1. **New Firm model** for organization-level accounts
2. **Two new roles**: `FIRM_ADMIN` and `FIRM_ADVISOR`
3. **Permission system** that respects firm boundaries
4. **Service layer** for firm management operations
5. **API endpoints** for firm CRUD operations
6. **Updated filtering** for engagements and tasks based on firm membership

The system preserves existing functionality for solo advisors while enabling multi-advisor firms with centralized management.

