"""
BBA (Business Benchmark Analysis) Service
Handles business logic for BBA projects
"""
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone

from app.models.bba import BBA
from app.models.diagnostic import Diagnostic
from app.models.engagement import Engagement
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

    def create_bba_from_diagnostic(
        self, diagnostic_id: UUID, user_id: UUID, force_new: bool = False
    ) -> BBA:
        """
        Create a BBA project from a completed diagnostic.

        Resolution order (unless force_new=True):
        1. If a BBA already exists for this exact diagnostic_id, return it.
        2. If a BBA with meaningful progress (max_step_reached >= 2) exists for the
           same engagement, re-link it to the new diagnostic and refresh context —
           preserving all step data so the user doesn't lose work.
        3. Otherwise create a brand-new BBA.
        """
        diagnostic = self.db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
        if not diagnostic:
            raise ValueError(f"Diagnostic {diagnostic_id} not found")
        if diagnostic.status != "completed":
            raise ValueError(f"Diagnostic must be completed (current status: {diagnostic.status})")

        diagnostic_context = {}
        if diagnostic.report_html:
            diagnostic_context["report_html"] = diagnostic.report_html
        if diagnostic.ai_analysis:
            diagnostic_context["ai_analysis"] = diagnostic.ai_analysis

        # Pull business name from the engagement so it can be used to prefill client_name
        business_name: Optional[str] = None
        if diagnostic.engagement_id:
            eng = self.db.query(Engagement).filter(Engagement.id == diagnostic.engagement_id).first()
            if eng and eng.business_name:
                business_name = eng.business_name
                diagnostic_context["business_name"] = business_name

        if not force_new:
            # 1. Exact diagnostic match (existing idempotent behaviour)
            existing = self.get_bba_by_diagnostic(diagnostic_id)
            if existing:
                logger.info(f"BBA project already exists for diagnostic {diagnostic_id}: {existing.id}")
                return existing

            # 2. Re-link most-progressed BBA from the same engagement
            if diagnostic.engagement_id:
                progressed = self.find_most_progressed_bba(diagnostic.engagement_id, user_id)
                if progressed and (progressed.max_step_reached or 0) >= 2:
                    logger.info(
                        f"Re-linking BBA {progressed.id} (step {progressed.max_step_reached}) "
                        f"from old diagnostic {progressed.diagnostic_id} to new diagnostic {diagnostic_id}"
                    )
                    progressed.diagnostic_id = diagnostic_id
                    progressed.diagnostic_context = diagnostic_context or None
                    if business_name and not progressed.client_name:
                        progressed.client_name = business_name
                    progressed.updated_at = datetime.now(timezone.utc)
                    self.db.commit()
                    self.db.refresh(progressed)
                    return progressed

        # 3. force_new: reset existing BBA row if one exists, otherwise create new
        if force_new and diagnostic.engagement_id:
            existing = self.find_most_progressed_bba(diagnostic.engagement_id, user_id)
            if existing:
                self._reset_bba(existing, diagnostic_id, diagnostic_context, business_name=business_name)
                logger.info(f"Reset BBA {existing.id} for fresh start from diagnostic {diagnostic_id}")
                return existing

        bba = BBA(
            created_by_user_id=user_id,
            engagement_id=diagnostic.engagement_id,
            diagnostic_id=diagnostic_id,
            diagnostic_context=diagnostic_context or None,
            status="uploaded",
            client_name=business_name,
        )
        self.db.add(bba)
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Created BBA project {bba.id} from diagnostic {diagnostic_id} for user {user_id}")
        return bba

    def _reset_bba(self, bba: BBA, diagnostic_id: UUID, diagnostic_context: dict, business_name: Optional[str] = None) -> None:
        """
        Wipe all step data on an existing BBA row so it can be reused
        for a fresh start. Keeps the same ID, engagement, and user.
        """
        bba.diagnostic_id = diagnostic_id
        bba.diagnostic_context = diagnostic_context or None
        bba.status = "uploaded"
        bba.current_step = None
        bba.max_step_reached = None
        # Step 1
        bba.file_ids = None
        bba.file_mappings = None
        bba.stored_files = None
        # Step 2
        bba.client_name = business_name
        bba.industry = None
        bba.company_size = None
        bba.locations = None
        bba.exclusions = None
        bba.constraints = None
        bba.preferred_ranking = None
        bba.strategic_priorities = None
        bba.exclude_sale_readiness = False
        # Step 3
        bba.draft_findings = None
        bba.draft_findings_edited = False
        # Step 4
        bba.expanded_findings = None
        # Step 5
        bba.snapshot_table = None
        # Step 6
        bba.twelve_month_plan = None
        bba.plan_notes = None
        # Step 7
        bba.executive_summary = None
        bba.final_report = None
        bba.report_version = 1
        # Phase 2 & 3
        bba.task_planner_settings = None
        bba.task_planner_tasks = None
        bba.task_planner_summary = None
        bba.presentation_slides = None
        # AI metadata
        bba.conversation_history = None
        bba.ai_model_used = None
        bba.ai_tokens_used = None
        bba.questionnaire_completed_at = None
        bba.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(bba)

    def find_most_progressed_bba(self, engagement_id: UUID, user_id: UUID) -> Optional[BBA]:
        """
        Find the BBA with the most progress for an engagement.
        Uses max_step_reached as primary sort, updated_at as tiebreaker.
        """
        bbas = self.get_bbas_by_engagement(engagement_id, user_id)
        if not bbas:
            return None
        return max(bbas, key=lambda b: (b.max_step_reached or 0, b.updated_at or b.created_at))

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
    
    def get_bba_by_diagnostic(self, diagnostic_id: UUID) -> Optional[BBA]:
        """
        Get BBA project by diagnostic ID (when created from that diagnostic).
        """
        return self.db.query(BBA).filter(
            BBA.diagnostic_id == diagnostic_id
        ).order_by(BBA.created_at.desc()).first()

    def get_bbas_by_engagement(self, engagement_id: UUID, user_id: UUID) -> List[BBA]:
        """
        Get all BBA projects for an engagement (for the given user).
        """
        return self.db.query(BBA).filter(
            BBA.engagement_id == engagement_id,
            BBA.created_by_user_id == user_id
        ).order_by(BBA.created_at.desc()).all()

    def get_bba_by_engagement(self, engagement_id: UUID, user_id: UUID) -> Optional[BBA]:
        """
        Get first BBA project by engagement ID (for backward compatibility).
        Prefer get_bbas_by_engagement when multiple BBAs per engagement are possible.
        """
        bbas = self.get_bbas_by_engagement(engagement_id, user_id)
        return bbas[0] if bbas else None
    
    def update_files(
        self,
        bba_id: UUID,
        file_ids: List[str],
        file_mappings: dict,
        stored_files: Optional[dict] = None,
    ) -> Optional[BBA]:
        """
        Update BBA with uploaded file information (Step 1).
        stored_files: optional dict mapping filename to relative storage path for persisted copies.
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None

        bba.file_ids = file_ids
        bba.file_mappings = file_mappings
        if stored_files is not None:
            existing_stored = bba.stored_files or {}
            bba.stored_files = {**existing_stored, **stored_files}
        bba.status = 'uploaded'
        bba.updated_at = datetime.now(timezone.utc)

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
        bba.questionnaire_completed_at = datetime.now(timezone.utc)
        bba.updated_at = datetime.now(timezone.utc)
        
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
        bba.updated_at = datetime.now(timezone.utc)
        
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
            # Build old-rank-to-new-rank mapping before overwriting
            old_findings = (bba.draft_findings or {}).get('findings', [])
            new_findings = edited_findings.get('findings', [])
            self._reorder_downstream_data(bba, old_findings, new_findings)

            bba.draft_findings = edited_findings
            bba.draft_findings_edited = True

        bba.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Confirmed draft findings for BBA {bba_id}")
        return bba
    
    def _reorder_downstream_data(self, bba, old_findings: list, new_findings: list):
        """
        Reorder expanded_findings, snapshot_table, and twelve_month_plan
        to match the new draft findings order. Matches items by title.
        """
        # Build mapping: title -> new_rank
        title_to_new_rank = {}
        for f in new_findings:
            title_to_new_rank[f.get('title', '')] = f.get('rank')

        logger.info(
            "Reordering downstream data for BBA %s – title_to_new_rank: %s",
            bba.id, title_to_new_rank,
        )

        # Reorder expanded_findings
        if bba.expanded_findings:
            ef_data = dict(bba.expanded_findings)
            ef_list = list(ef_data.get('expanded_findings', []))
            if ef_list:
                for item in ef_list:
                    new_rank = title_to_new_rank.get(item.get('title'))
                    if new_rank is not None:
                        item['rank'] = new_rank
                ef_list.sort(key=lambda x: x.get('rank', 999))
                ef_data['expanded_findings'] = ef_list
                bba.expanded_findings = ef_data
                flag_modified(bba, "expanded_findings")
                logger.info("Reordered %d expanded findings", len(ef_list))

        # Reorder snapshot_table
        if bba.snapshot_table:
            st = dict(bba.snapshot_table)
            inner = st.get('snapshot_table')
            if isinstance(inner, dict):
                rows = list(inner.get('rows', []))
            else:
                rows = list(st.get('rows', []))

            if rows:
                # Snapshot rows don't have title — map via old_rank -> title -> new_rank
                old_rank_to_title = {f.get('rank'): f.get('title', '') for f in old_findings}
                for row in rows:
                    old_title = old_rank_to_title.get(row.get('rank'), '')
                    new_rank = title_to_new_rank.get(old_title)
                    if new_rank is not None:
                        row['rank'] = new_rank
                rows.sort(key=lambda x: x.get('rank', 999))

                if isinstance(inner, dict):
                    inner['rows'] = rows
                    st['snapshot_table'] = inner
                else:
                    st['rows'] = rows
                bba.snapshot_table = st
                flag_modified(bba, "snapshot_table")
                logger.info("Reordered %d snapshot rows", len(rows))

        # Reorder twelve_month_plan
        if bba.twelve_month_plan:
            plan = dict(bba.twelve_month_plan)
            recs = list(plan.get('recommendations', []))
            if recs:
                for rec in recs:
                    new_rank = title_to_new_rank.get(rec.get('title'))
                    if new_rank is not None:
                        rec['number'] = new_rank
                recs.sort(key=lambda x: x.get('number', 999))
                plan['recommendations'] = recs

                # Also reorder timeline_summary rows
                ts = plan.get('timeline_summary', {})
                if ts:
                    ts = dict(ts)
                    ts_rows = list(ts.get('rows', []))
                    if ts_rows:
                        # Match timeline rows by recommendation title
                        new_num_by_title = {r.get('title', ''): r.get('number') for r in recs}
                        for row in ts_rows:
                            new_num = new_num_by_title.get(row.get('recommendation'))
                            if new_num is not None:
                                row['rec_number'] = new_num
                        ts_rows.sort(key=lambda x: x.get('rec_number', 999))
                        ts['rows'] = ts_rows
                    plan['timeline_summary'] = ts

                bba.twelve_month_plan = plan
                flag_modified(bba, "twelve_month_plan")
                logger.info("Reordered %d recommendations", len(recs))

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
        bba.updated_at = datetime.now(timezone.utc)
        
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
        bba.updated_at = datetime.now(timezone.utc)
        
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
        bba.updated_at = datetime.now(timezone.utc)
        
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
        bba.updated_at = datetime.now(timezone.utc)
        
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
        bba.updated_at = datetime.now(timezone.utc)
        
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
        
        bba.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Applied edits to BBA {bba_id}")
        return bba
    
    def update_step_progress(
        self,
        bba_id: UUID,
        current_step: Optional[int] = None,
        max_step_reached: Optional[int] = None
    ) -> Optional[BBA]:
        """
        Update BBA step progress markers
        
        Args:
            bba_id: BBA project ID
            current_step: Current step the user is on (1-9)
            max_step_reached: Maximum step the user has reached (1-9)
            
        Returns:
            Updated BBA object or None if not found
        """
        bba = self.get_bba(bba_id)
        if not bba:
            return None
        
        if current_step is not None:
            bba.current_step = current_step
        if max_step_reached is not None:
            bba.max_step_reached = max_step_reached
        
        bba.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(bba)
        logger.info(f"Updated BBA {bba_id} step progress: current={current_step}, max={max_step_reached}")
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

