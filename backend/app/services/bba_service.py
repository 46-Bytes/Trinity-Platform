"""
BBA (Business Benchmark Analysis) Service
Handles business logic for BBA projects
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from app.models.bba import BBA
from app.schemas.bba import BBACreate, BBAUpdate, BBAFileUpload, BBAQuestionnaire
import logging

logger = logging.getLogger(__name__)


class BBAService:
    """Service for managing BBA projects"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_bba(self, user_id: UUID, engagement_id: Optional[UUID] = None) -> BBA:
        """
        Create a new BBA project
        
        Args:
            user_id: ID of user creating the project
            engagement_id: Optional engagement ID to link to
            
        Returns:
            Created BBA object
        """
        bba = BBA(
            created_by_user_id=user_id,
            engagement_id=engagement_id,
            status='uploaded'
        )
        self.db.add(bba)
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Created BBA project {bba.id} for user {user_id}")
        return bba
    
    def get_bba(self, bba_id: UUID) -> Optional[BBA]:
        """
        Get BBA by ID
        
        Args:
            bba_id: BBA project ID
            
        Returns:
            BBA object or None
        """
        return self.db.query(BBA).filter(BBA.id == bba_id).first()
    
    def get_user_bba_projects(self, user_id: UUID) -> List[BBA]:
        """
        Get all BBA projects for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of BBA projects
        """
        return self.db.query(BBA).filter(
            BBA.created_by_user_id == user_id
        ).order_by(BBA.created_at.desc()).all()
    
    def update_files(self, bba_id: UUID, file_ids: List[str], file_mappings: dict) -> Optional[BBA]:
        """
        Update BBA with uploaded file information (Step 1)
        
        Args:
            bba_id: BBA project ID
            file_ids: List of OpenAI file IDs
            file_mappings: Dictionary mapping filename to file_id
            
        Returns:
            Updated BBA object or None if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None
        
        bba.file_ids = file_ids
        bba.file_mappings = file_mappings
        bba.status = 'uploaded'
        bba.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Updated BBA {bba_id} with {len(file_ids)} files")
        return bba
    
    def update_questionnaire(self, bba_id: UUID, questionnaire: BBAQuestionnaire) -> Optional[BBA]:
        """
        Update BBA with questionnaire data (Step 2)
        
        Args:
            bba_id: BBA project ID
            questionnaire: Questionnaire data
            
        Returns:
            Updated BBA object or None if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None
        
        bba.client_name = questionnaire.client_name
        bba.industry = questionnaire.industry
        bba.company_size = questionnaire.company_size
        bba.locations = questionnaire.locations
        bba.exclusions = questionnaire.exclusions
        bba.constraints = questionnaire.constraints
        bba.preferred_ranking = questionnaire.preferred_ranking
        bba.strategic_priorities = questionnaire.strategic_priorities
        bba.exclude_sale_readiness = questionnaire.exclude_sale_readiness
        bba.status = 'questionnaire_completed'
        bba.questionnaire_completed_at = datetime.utcnow()
        bba.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Updated BBA {bba_id} with questionnaire data")
        return bba
    
    def delete_bba(self, bba_id: UUID) -> bool:
        """
        Delete BBA project
        
        Args:
            bba_id: BBA project ID
            
        Returns:
            True if deleted, False if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return False
        
        self.db.delete(bba)
        self.db.commit()
        logger.info(f"Deleted BBA project {bba_id}")
        return True


def get_bba_service(db: Session) -> BBAService:
    """Dependency function to get BBA service"""
    return BBAService(db)

