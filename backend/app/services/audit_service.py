"""
Audit logging service for tracking impersonation events.
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class AuditService:
    """Service for logging audit events, particularly impersonation activities."""
    
    @staticmethod
    def log_impersonation_start(
        original_user_id: UUID,
        impersonated_user_id: UUID,
        session_id: UUID,
        db: Session
    ) -> None:
        """
        Log the start of an impersonation session.
        
        Args:
            original_user_id: The superadmin user who is impersonating
            impersonated_user_id: The user being impersonated
            session_id: The impersonation session ID
            db: Database session
        """
        try:
            logger.info(
                f"IMPERSONATION START: Session {session_id} - "
                f"Superadmin {original_user_id} started impersonating user {impersonated_user_id} "
                f"at {datetime.utcnow().isoformat()}"
            )
            # In the future, this could write to a dedicated audit_log table
            # For now, we use application logs which can be aggregated
        except Exception as e:
            logger.error(f"Failed to log impersonation start: {str(e)}")
    
    @staticmethod
    def log_impersonation_end(
        session_id: UUID,
        original_user_id: UUID,
        db: Session
    ) -> None:
        """
        Log the end of an impersonation session.
        
        Args:
            session_id: The impersonation session ID
            original_user_id: The superadmin user who was impersonating
            db: Database session
        """
        try:
            logger.info(
                f"IMPERSONATION END: Session {session_id} - "
                f"Superadmin {original_user_id} ended impersonation "
                f"at {datetime.utcnow().isoformat()}"
            )
            # In the future, this could write to a dedicated audit_log table
            # For now, we use application logs which can be aggregated
        except Exception as e:
            logger.error(f"Failed to log impersonation end: {str(e)}")
    
    @staticmethod
    def log_impersonation_action(
        session_id: UUID,
        original_user_id: UUID,
        action: str,
        details: Optional[dict] = None
    ) -> None:
        """
        Log an action taken during impersonation.
        
        Args:
            session_id: The impersonation session ID
            original_user_id: The superadmin user who is impersonating
            action: Description of the action taken
            details: Optional additional details about the action
        """
        try:
            details_str = f" - Details: {details}" if details else ""
            logger.info(
                f"IMPERSONATION ACTION: Session {session_id} - "
                f"Superadmin {original_user_id} performed action: {action}"
                f"{details_str} at {datetime.utcnow().isoformat()}"
            )
        except Exception as e:
            logger.error(f"Failed to log impersonation action: {str(e)}")

