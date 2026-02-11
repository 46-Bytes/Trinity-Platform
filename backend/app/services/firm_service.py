"""
Firm service for managing firm accounts and advisors.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
import uuid as uuid_lib
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from datetime import datetime, timedelta
import logging

from ..models.firm import Firm
from ..models.user import User, UserRole
from ..models.engagement import Engagement
from ..models.subscription import Subscription
from ..models.adv_client import AdvisorClient
from ..services.firm_permissions import (
    can_manage_firm_users,
    can_view_firm_engagements,
    can_assign_advisors,
    can_modify_subscription
)
from ..services.auth0_management import Auth0Management
from ..services.email_service import EmailService


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
        billing_email: Optional[str] = None,
        subscription_id: Optional[UUID] = None
    ) -> Firm:
        """
        Create a new firm account.
        
        Args:
            firm_name: Name of the firm
            firm_admin_id: User ID of the Firm Admin
            seat_count: Number of seats (minimum 5)
            billing_email: Email for billing notifications
            subscription_plan: Subscription plan name (e.g., 'professional', 'enterprise')
            
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
        
        # If subscription_id is provided, use existing subscription
        if subscription_id:
            subscription = self.db.query(Subscription).filter(Subscription.id == subscription_id).first()
            if not subscription:
                raise ValueError(f"Subscription {subscription_id} not found")
            # Use subscription details (multiple firms can share the same subscription)
            plan_name = subscription.plan_name
        else:
            raise ValueError("subscription_id is required when creating a firm")
        
        # Create firm
        firm = Firm(
            firm_name=firm_name,
            firm_admin_id=firm_admin_id,
            seat_count=seat_count,
            seats_used=0,
            billing_email=billing_email or firm_admin.email,
            subscription_plan=plan_name,
            is_active=True
        )
        
        self.db.add(firm)
        self.db.flush()  # Get firm.id
        
        # Update firm admin
        firm_admin.firm_id = firm.id
        firm_admin.role = UserRole.FIRM_ADMIN
        
        # Link existing subscription to firm
        firm.subscription_id = subscription.id
        
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
            existing_role = advisor.role.value if hasattr(advisor.role, "value") else str(advisor.role)
            raise ValueError(
                f"User with email {advisor_email} already exists. "
                "Please use a different email."
            )
        else:
            # Create advisor user in Auth0 (this will send the password setup email)
            try:
                self.logger.info(f"Creating new firm advisor in Auth0: {advisor_email}")
                # Split advisor_name into first/last if possible
                first_name = None
                last_name = None
                if advisor_name:
                    parts = advisor_name.strip().split(" ", 1)
                    first_name = parts[0]
                    if len(parts) > 1:
                        last_name = parts[1]

                auth0_user = Auth0Management.create_user(
                    email=advisor_email,
                    role=UserRole.FIRM_ADVISOR.value,
                    first_name=first_name,
                    last_name=last_name,
                )
                auth0_id = auth0_user["user_id"]
                self.logger.info(f"✅ Firm advisor created in Auth0 with ID: {auth0_id}. Password setup email sent.")
            except Exception as e:
                self.logger.error(f"❌ Failed to create firm advisor in Auth0: {str(e)}")
                raise ValueError(f"Failed to create firm advisor account: {str(e)}")
            
            # Create new advisor user in local database with real Auth0 ID
            advisor = User(
                auth0_id=auth0_id,
                email=advisor_email,
                name=advisor_name,
                first_name=first_name,
                last_name=last_name,
                role=UserRole.FIRM_ADVISOR,
                firm_id=firm_id,
                is_active=True,
                email_verified=False,
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
        # Allow super admin, admin, firm admin, and firm advisor (from same firm) to view advisors
        if current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
            pass  # Super admin and admin have access
        elif current_user.role == UserRole.FIRM_ADMIN and current_user.firm_id == firm_id:
            pass  # Firm admin can view advisors in their firm
        elif current_user.role == UserRole.FIRM_ADVISOR and current_user.firm_id == firm_id:
            pass  # Firm advisor can view advisors in their own firm
        else:
            raise ValueError("Insufficient permissions")
        
        # Return FIRM_ADVISOR as they can both be secondary advisors
        return self.db.query(User).filter(
            User.firm_id == firm_id,
            User.role.in_([UserRole.FIRM_ADVISOR]),
            User.is_active == True
        ).all()
    
    def get_advisor_engagements(self, firm_id: UUID, advisor_id: UUID, current_user: User) -> Dict[str, List[Engagement]]:
        """
        Get all engagements where an advisor is involved (primary or secondary).
        
        Returns:
            Dict with 'primary' and 'secondary' keys containing lists of engagements
        """
        if not can_view_firm_engagements(current_user, firm_id):
            raise ValueError("Insufficient permissions")
        
        advisor = self.db.query(User).filter(User.id == advisor_id).first()
        if not advisor or advisor.firm_id != firm_id:
            raise ValueError("Advisor not found in firm")
        
        # Get engagements where advisor is primary (exclude soft-deleted)
        primary_engagements = self.db.query(Engagement).filter(
            Engagement.primary_advisor_id == advisor_id,
            Engagement.firm_id == firm_id,
            Engagement.is_deleted == False,  # only non-deleted engagements
        ).all()
        
        # Get engagements where advisor is secondary (exclude soft-deleted)
        secondary_engagements = self.db.query(Engagement).filter(
            Engagement.firm_id == firm_id,
            Engagement.is_deleted == False,  # only non-deleted engagements
        ).all()
        
        # Filter to only those where advisor is in secondary_advisor_ids
        secondary_list = [
            eng for eng in secondary_engagements
            if eng.secondary_advisor_ids and advisor_id in eng.secondary_advisor_ids
        ]
        
        return {
            "primary": primary_engagements,
            "secondary": secondary_list
        }
    
    def suspend_advisor(
        self,
        firm_id: UUID,
        advisor_id: UUID,
        suspended_by_user_id: UUID,
        reassignments: Optional[Dict[UUID, UUID]] = None
    ) -> User:
        """
        Suspend an advisor (temporary deactivation).
        
        Args:
            firm_id: Firm ID
            advisor_id: Advisor to suspend
            suspended_by_user_id: User performing the suspension
            reassignments: Dict mapping engagement_id -> new_primary_advisor_id for primary engagements
        
        Returns:
            Suspended User object
        """
        # Check permissions
        suspended_by = self.db.query(User).filter(User.id == suspended_by_user_id).first()
        if not can_manage_firm_users(suspended_by, firm_id):
            raise ValueError("Only Firm Admins can suspend advisors")
        
        firm = self.db.query(Firm).filter(Firm.id == firm_id).first()
        advisor = self.db.query(User).filter(User.id == advisor_id).first()
        
        if not advisor or advisor.firm_id != firm_id:
            raise ValueError("Advisor not found in firm")
        
        if advisor.role == UserRole.FIRM_ADMIN:
            raise ValueError("Cannot suspend Firm Admin")
        
        if not advisor.is_active:
            raise ValueError("Advisor is already suspended")
        
        # Get all active advisors in firm (excluding the one being suspended)
        active_advisors = self.db.query(User).filter(
            User.firm_id == firm_id,
            User.role.in_([UserRole.FIRM_ADMIN, UserRole.FIRM_ADVISOR]),
            User.is_active == True,
            User.id != advisor_id
        ).all()
        
        # Get engagements where advisor is primary
        primary_engagements = self.db.query(Engagement).filter(
            Engagement.primary_advisor_id == advisor_id,
            Engagement.firm_id == firm_id
        ).all()
        
        # Handle primary advisor reassignments
        if primary_engagements:
            if not reassignments:
                raise ValueError("Reassignments required for primary advisor engagements")
            
            for engagement in primary_engagements:
                new_advisor_id = reassignments.get(engagement.id)
                if not new_advisor_id:
                    raise ValueError(f"Reassignment required for engagement {engagement.id}")
                
                # Verify new advisor is active and in the same firm
                new_advisor = self.db.query(User).filter(
                    User.id == new_advisor_id,
                    User.firm_id == firm_id,
                    User.is_active == True
                ).first()
                
                if not new_advisor:
                    raise ValueError(f"New advisor {new_advisor_id} not found or not active in firm")
                
                # Reassign
                engagement.primary_advisor_id = new_advisor_id
                
                # Remove old advisor from secondary if present
                if engagement.secondary_advisor_ids and advisor_id in engagement.secondary_advisor_ids:
                    engagement.secondary_advisor_ids = [
                        aid for aid in engagement.secondary_advisor_ids if aid != advisor_id
                    ]
        
        # Remove from secondary advisor lists
        secondary_engagements = self.db.query(Engagement).filter(
            Engagement.firm_id == firm_id
        ).all()
        
        for engagement in secondary_engagements:
            if engagement.secondary_advisor_ids and advisor_id in engagement.secondary_advisor_ids:
                engagement.secondary_advisor_ids = [
                    aid for aid in engagement.secondary_advisor_ids if aid != advisor_id
                ]
        
        # Suspend advisor (keep in firm but deactivate)
        # NOTE: Do NOT decrement seats_used - suspended advisors still count as seats
        advisor.is_active = False
        
        self.db.commit()
        self.db.refresh(advisor)
        
        self.logger.info(f"Advisor {advisor_id} suspended in firm {firm_id}")
        return advisor
    
    def reactivate_advisor(
        self,
        firm_id: UUID,
        advisor_id: UUID,
        reactivated_by_user_id: UUID
    ) -> User:
        """
        Reactivate a suspended advisor.
        
        Args:
            firm_id: Firm ID
            advisor_id: Advisor to reactivate
            reactivated_by_user_id: User performing the reactivation
        
        Returns:
            Reactivated User object
        """
        # Check permissions
        reactivated_by = self.db.query(User).filter(User.id == reactivated_by_user_id).first()
        if not can_manage_firm_users(reactivated_by, firm_id):
            raise ValueError("Only Firm Admins can reactivate advisors")
        
        advisor = self.db.query(User).filter(User.id == advisor_id).first()
        
        if not advisor or advisor.firm_id != firm_id:
            raise ValueError("Advisor not found in firm")
        
        if advisor.role == UserRole.FIRM_ADMIN:
            raise ValueError("Cannot reactivate Firm Admin (they should always be active)")
        
        if advisor.is_active:
            raise ValueError("Advisor is already active")
        
        # Reactivate advisor
        advisor.is_active = True
        
        self.db.commit()
        self.db.refresh(advisor)
        
        self.logger.info(f"Advisor {advisor_id} reactivated in firm {firm_id}")
        return advisor
    
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
        
        # Update subscription via firm's subscription_id
        if firm.subscription_id:
            subscription = self.db.query(Subscription).filter(
                Subscription.id == firm.subscription_id
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
    
    def add_client_to_firm(
        self,
        firm_id: UUID,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        added_by: UUID = None,
        primary_advisor_id: Optional[UUID] = None
    ) -> User:
        """
        Add a client to a firm.
        
        If the client doesn't exist, creates a new user with CLIENT role.
        If the client exists, associates them with the firm.
        Adds the client ID to the firm's clients array.
        Optionally creates an AdvisorClient association if primary_advisor_id is provided.
        
        Args:
            firm_id: ID of the firm
            email: Email address of the client
            first_name: First name (optional)
            last_name: Last name (optional)
            added_by: ID of the user adding the client (for permissions)
            primary_advisor_id: Optional primary advisor ID to associate with the client
            
        Returns:
            User object (client)
        """
        # Verify firm exists
        firm = self.db.query(Firm).filter(Firm.id == firm_id).first()
        if not firm:
            raise ValueError("Firm not found")
        
        # Check permissions if added_by is provided
        if added_by:
            adder = self.db.query(User).filter(User.id == added_by).first()
            if not adder:
                raise ValueError("User not found")
            # Super admin can add clients to any firm
            if adder.role == UserRole.SUPER_ADMIN:
                pass  # Super admin has permission
            elif adder.role not in [UserRole.FIRM_ADMIN, UserRole.ADMIN]:
                raise ValueError("Only Firm Admins and Super Admins can add clients")
            elif adder.firm_id != firm_id:
                raise ValueError("Insufficient permissions to add clients to this firm")
        
        # Check if client already exists
        client = self.db.query(User).filter(User.email == email).first()

        derived_name: Optional[str] = None
        if first_name and last_name:
            derived_name = f"{first_name} {last_name}".strip()
        elif first_name:
            derived_name = first_name.strip()
        elif last_name:
            derived_name = last_name.strip()
        
        if client:
            # If the user already belongs to a (different) firm, do NOT move them
            if client.firm_id and client.firm_id != firm_id:
                raise ValueError("User with this email is already part of another firm")

            # If this client is already linked to this firm via the clients array, don't duplicate
            if firm.clients and client.id in firm.clients:
                raise ValueError("Client is already associated with this firm")

            if client.role != UserRole.CLIENT:
                raise ValueError(
                    f"User with email {email} already exists "
                    "and cannot be added as a firm client."
                )

            # Safe updates (names) while keeping their role as client
            client.firm_id = firm_id
            if first_name:
                client.first_name = first_name
            if last_name:
                client.last_name = last_name
            if derived_name:
                client.name = derived_name
            
            # If client has a temp auth0_id, create them in Auth0 and update it
            if client.auth0_id and client.auth0_id.startswith("temp_client_"):
                try:
                    self.logger.info(f"Client {email} has temp auth0_id, creating in Auth0...")
                    auth0_user = Auth0Management.create_user(
                        email=email,
                        role=UserRole.CLIENT.value,
                        first_name=client.first_name,
                        last_name=client.last_name
                    )
                    client.auth0_id = auth0_user["user_id"]
                    self.logger.info(f"✅ Client created in Auth0 with ID: {client.auth0_id}. Password setup email sent.")
                except Exception as e:
                    # If user already exists in Auth0, try to find their auth0_id
                    if "already exists" in str(e).lower() or "409" in str(e):
                        self.logger.warning(f"Client {email} already exists in Auth0. Skipping Auth0 creation.")
                    else:
                        self.logger.error(f"❌ Failed to create client in Auth0: {str(e)}")
                        # Don't fail the whole operation, just log the error
                        # The client will still be added to the firm, but without Auth0 account
        else:
            # Create new client user in Auth0 (this will send the password setup email)
            try:
                self.logger.info(f"Creating new client in Auth0: {email}")
                auth0_user = Auth0Management.create_user(
                    email=email,
                    role=UserRole.CLIENT.value,
                    first_name=first_name,
                    last_name=last_name
                )
                auth0_id = auth0_user["user_id"]
                self.logger.info(f"✅ Client created in Auth0 with ID: {auth0_id}. Password setup email sent.")
            except Exception as e:
                self.logger.error(f"❌ Failed to create client in Auth0: {str(e)}")
                raise ValueError(f"Failed to create client account: {str(e)}")
            
            # Create new client user in local database with real Auth0 ID
            client = User(
                email=email,
                auth0_id=auth0_id,  # Use real Auth0 ID instead of temp
                name=derived_name,
                first_name=first_name,
                last_name=last_name,
                role=UserRole.CLIENT,
                firm_id=firm_id,
                email_verified=False,
                is_active=True
            )
            self.db.add(client)
            self.db.flush()  # Flush to get the client ID before adding to array
        
        # Initialize clients array if None
        if firm.clients is None:
            firm.clients = []
        
        # Add client ID to firm's clients array if not already present
        if client.id not in firm.clients:
            firm.clients.append(client.id)
            # Mark the array as modified for SQLAlchemy to detect changes
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(firm, "clients")
        
        # Create AdvisorClient association if primary_advisor_id is provided
        if primary_advisor_id:
            # Validate that advisor exists, belongs to the same firm, and is a FIRM_ADVISOR
            advisor = self.db.query(User).filter(User.id == primary_advisor_id).first()
            if not advisor:
                raise ValueError(f"Advisor with ID {primary_advisor_id} not found")
            if advisor.firm_id != firm_id:
                raise ValueError("Advisor must belong to the same firm as the client")
            if advisor.role != UserRole.FIRM_ADVISOR:
                raise ValueError("Primary advisor must be a FIRM_ADVISOR (cannot be FIRM_ADMIN)")
            if not advisor.is_active:
                raise ValueError("Advisor must be active")
            
            # Check if association already exists
            existing_association = self.db.query(AdvisorClient).filter(
                AdvisorClient.advisor_id == primary_advisor_id,
                AdvisorClient.client_id == client.id
            ).first()
            
            if not existing_association:
                # Create new association
                association = AdvisorClient(
                    advisor_id=primary_advisor_id,
                    client_id=client.id,
                    status='active'
                )
                self.db.add(association)
                self.logger.info(f"Created AdvisorClient association: advisor {primary_advisor_id} <-> client {client.id}")

            # Send notification email to advisor about the new client assignment
            try:
                EmailService.send_client_added_notification(
                    advisor_email=advisor.email,
                    advisor_name=advisor.name or advisor.first_name,
                    client_name=client.name,
                    client_email=client.email,
                    firm_name=firm.firm_name,
                )
                self.logger.info(
                    f"Sent client-added notification email to advisor {advisor.email} for client {client.email}"
                )
            except Exception as e:
                # Log but do not fail the client creation if email fails
                self.logger.warning(
                    f"Failed to send client-added notification email to advisor {advisor.email}: {e}"
                )
        
        self.db.commit()
        self.db.refresh(client)
        self.db.refresh(firm)
        
        self.logger.info(f"Client {client.id} added to firm {firm_id}")
        return client


def get_firm_service(db: Session) -> FirmService:
    """Factory function to create FirmService."""
    return FirmService(db)


