"""
Firm service for managing firm accounts and advisors.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from datetime import datetime, timedelta
import logging

from ..models.firm import Firm
from ..models.user import User, UserRole
from ..models.engagement import Engagement
from ..models.subscription import Subscription
from ..services.firm_permissions import (
    can_manage_firm_users,
    can_view_firm_engagements,
    can_assign_advisors,
    can_modify_subscription
)


class FirmService:
    """Service for managing firm accounts."""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    def create_firm(
        self,
        firm_name: str,
        firm_admin_id: UUID,
        seat_count: int = 5,
        billing_email: Optional[str] = None
    ) -> Firm:
        """
        Create a new firm account.
        
        Args:
            firm_name: Name of the firm
            firm_admin_id: User ID of the Firm Admin
            seat_count: Number of seats (minimum 5)
            billing_email: Email for billing notifications
            
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
            seats_used=1,  # Just the Firm Admin
            billing_email=billing_email or firm_admin.email,
            is_active=True
        )
        
        self.db.add(firm)
        self.db.flush()  # Get firm.id
        
        # Update firm admin
        firm_admin.firm_id = firm.id
        firm_admin.role = UserRole.FIRM_ADMIN
        
        # Create initial subscription
        subscription = Subscription(
            firm_id=firm.id,
            plan_name="professional",
            seat_count=seat_count,
            monthly_price=299.00,  # Base price per month
            status="active",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30)
        )
        self.db.add(subscription)
        
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
            # For now, create with placeholder auth0_id
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
        if not can_modify_subscription(updater, firm_id):
            raise ValueError("Only Firm Admins can update seat count")
        
        if new_seat_count < firm.seats_used:
            raise ValueError(f"Cannot reduce seats below current usage ({firm.seats_used})")
        
        if new_seat_count < 5:
            raise ValueError("Minimum seat count is 5")
        
        # Update firm seat count
        firm.seat_count = new_seat_count
        
        # Update subscription
        subscription = self.db.query(Subscription).filter(
            Subscription.firm_id == firm_id
        ).first()
        
        if subscription:
            # Recalculate monthly price (example: $299 base + $50 per additional seat)
            base_price = 299.00
            additional_seats = max(0, new_seat_count - 5)
            subscription.monthly_price = base_price + (additional_seats * 50.00)
            subscription.seat_count = new_seat_count
        
        self.db.commit()
        self.db.refresh(firm)
        
        # TODO: Trigger billing update webhook/API call to payment provider
        
        self.logger.info(f"Seat count updated for firm {firm_id}: {firm.seat_count} -> {new_seat_count}")
        return firm
    
    def reassign_engagement(
        self,
        engagement_id: UUID,
        new_primary_advisor_id: UUID,
        reassigned_by: UUID
    ) -> Engagement:
        """
        Reassign an engagement to a different advisor within the firm.
        
        Only Firm Admins can reassign engagements.
        """
        engagement = self.db.query(Engagement).filter(Engagement.id == engagement_id).first()
        if not engagement:
            raise ValueError("Engagement not found")
        
        if not engagement.firm_id:
            raise ValueError("Engagement is not part of a firm")
        
        # Check permissions
        reassigner = self.db.query(User).filter(User.id == reassigned_by).first()
        if not can_assign_advisors(reassigner, engagement.firm_id):
            raise ValueError("Only Firm Admins can reassign engagements")
        
        # Verify new advisor is in the same firm
        new_advisor = self.db.query(User).filter(User.id == new_primary_advisor_id).first()
        if not new_advisor or new_advisor.firm_id != engagement.firm_id:
            raise ValueError("New advisor must be in the same firm")
        
        # Reassign
        engagement.primary_advisor_id = new_primary_advisor_id
        
        # Remove old advisor from secondary if present
        old_advisor_id = engagement.primary_advisor_id
        if engagement.secondary_advisor_ids and old_advisor_id in engagement.secondary_advisor_ids:
            engagement.secondary_advisor_ids = [
                aid for aid in engagement.secondary_advisor_ids if aid != old_advisor_id
            ]
        
        self.db.commit()
        self.db.refresh(engagement)
        
        self.logger.info(f"Engagement {engagement_id} reassigned to {new_primary_advisor_id}")
        return engagement
    
    def get_firm_by_id(self, firm_id: UUID) -> Optional[Firm]:
        """Get firm by ID."""
        return self.db.query(Firm).filter(Firm.id == firm_id).first()
    
    def get_firm_by_admin_id(self, admin_id: UUID) -> Optional[Firm]:
        """Get firm by Firm Admin ID."""
        return self.db.query(Firm).filter(Firm.firm_admin_id == admin_id).first()


def get_firm_service(db: Session) -> FirmService:
    """Factory function to create FirmService."""
    return FirmService(db)


