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
    
    def update_draft_findings(
        self, 
        bba_id: UUID, 
        findings: dict, 
        tokens_used: int = 0,
        model: str = ""
    ) -> Optional[BBA]:
        """
        Update BBA with draft findings (Step 3)
        
        Args:
            bba_id: BBA project ID
            findings: Draft findings data
            tokens_used: Tokens used for generation
            model: Model used
            
        Returns:
            Updated BBA object or None if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None
        
        bba.draft_findings = findings
        bba.draft_findings_edited = False
        bba.status = 'draft_findings'
        bba.ai_model_used = model
        bba.ai_tokens_used = (bba.ai_tokens_used or 0) + tokens_used
        bba.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Updated BBA {bba_id} with draft findings")
        return bba
    
    def confirm_draft_findings(self, bba_id: UUID, edited_findings: Optional[dict] = None) -> Optional[BBA]:
        """
        Confirm draft findings (optionally with edits)
        
        Args:
            bba_id: BBA project ID
            edited_findings: Optional edited findings to save
            
        Returns:
            Updated BBA object or None if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None
        
        if edited_findings:
            bba.draft_findings = edited_findings
            bba.draft_findings_edited = True
        
        bba.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Confirmed draft findings for BBA {bba_id}")
        return bba
    
    def update_expanded_findings(
        self, 
        bba_id: UUID, 
        expanded_findings: dict,
        tokens_used: int = 0,
        model: str = ""
    ) -> Optional[BBA]:
        """
        Update BBA with expanded findings (Step 4)
        
        Args:
            bba_id: BBA project ID
            expanded_findings: Expanded findings data
            tokens_used: Tokens used for generation
            model: Model used
            
        Returns:
            Updated BBA object or None if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None
        
        bba.expanded_findings = expanded_findings
        bba.status = 'expanded_findings'
        bba.ai_model_used = model
        bba.ai_tokens_used = (bba.ai_tokens_used or 0) + tokens_used
        bba.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Updated BBA {bba_id} with expanded findings")
        return bba
    
    def update_snapshot_table(
        self, 
        bba_id: UUID, 
        snapshot_table: dict,
        tokens_used: int = 0,
        model: str = ""
    ) -> Optional[BBA]:
        """
        Update BBA with snapshot table (Step 5)
        
        Args:
            bba_id: BBA project ID
            snapshot_table: Snapshot table data
            tokens_used: Tokens used for generation
            model: Model used
            
        Returns:
            Updated BBA object or None if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None
        
        bba.snapshot_table = snapshot_table
        bba.status = 'snapshot_table'
        bba.ai_model_used = model
        bba.ai_tokens_used = (bba.ai_tokens_used or 0) + tokens_used
        bba.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Updated BBA {bba_id} with snapshot table")
        return bba
    
    def update_twelve_month_plan(
        self, 
        bba_id: UUID, 
        twelve_month_plan: dict,
        plan_notes: Optional[str] = None,
        tokens_used: int = 0,
        model: str = ""
    ) -> Optional[BBA]:
        """
        Update BBA with 12-month plan (Step 6)
        
        Args:
            bba_id: BBA project ID
            twelve_month_plan: 12-month plan data
            plan_notes: Optional plan notes/disclaimer
            tokens_used: Tokens used for generation
            model: Model used
            
        Returns:
            Updated BBA object or None if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None
        
        bba.twelve_month_plan = twelve_month_plan
        if plan_notes:
            bba.plan_notes = plan_notes
        bba.status = 'twelve_month_plan'
        bba.ai_model_used = model
        bba.ai_tokens_used = (bba.ai_tokens_used or 0) + tokens_used
        bba.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Updated BBA {bba_id} with 12-month plan")
        return bba
    
    def update_executive_summary(
        self, 
        bba_id: UUID, 
        executive_summary: str,
        tokens_used: int = 0,
        model: str = ""
    ) -> Optional[BBA]:
        """
        Update BBA with executive summary
        
        Args:
            bba_id: BBA project ID
            executive_summary: Executive summary text
            tokens_used: Tokens used for generation
            model: Model used
            
        Returns:
            Updated BBA object or None if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None
        
        bba.executive_summary = executive_summary
        bba.ai_model_used = model
        bba.ai_tokens_used = (bba.ai_tokens_used or 0) + tokens_used
        bba.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Updated BBA {bba_id} with executive summary")
        return bba
    
    def update_final_report(
        self, 
        bba_id: UUID, 
        final_report: dict,
        increment_version: bool = True
    ) -> Optional[BBA]:
        """
        Update BBA with final compiled report (Step 7)
        
        Args:
            bba_id: BBA project ID
            final_report: Complete report data
            increment_version: Whether to increment version number
            
        Returns:
            Updated BBA object or None if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None
        
        bba.final_report = final_report
        bba.status = 'completed'
        if increment_version:
            bba.report_version = (bba.report_version or 0) + 1
        bba.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Updated BBA {bba_id} with final report (version {bba.report_version})")
        return bba
    
    def apply_edits(
        self, 
        bba_id: UUID, 
        updated_sections: dict
    ) -> Optional[BBA]:
        """
        Apply edits to BBA sections (Step 7 review)
        
        Args:
            bba_id: BBA project ID
            updated_sections: Dict with section names and updated data
            
        Returns:
            Updated BBA object or None if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None
        
        # Update only the sections that are provided
        if 'draft_findings' in updated_sections:
            bba.draft_findings = updated_sections['draft_findings']
            bba.draft_findings_edited = True
        
        if 'expanded_findings' in updated_sections:
            bba.expanded_findings = updated_sections['expanded_findings']
        
        if 'snapshot_table' in updated_sections:
            bba.snapshot_table = updated_sections['snapshot_table']
        
        if 'twelve_month_plan' in updated_sections:
            bba.twelve_month_plan = updated_sections['twelve_month_plan']
        
        if 'executive_summary' in updated_sections:
            bba.executive_summary = updated_sections['executive_summary']
        
        bba.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Applied edits to BBA {bba_id}")
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

