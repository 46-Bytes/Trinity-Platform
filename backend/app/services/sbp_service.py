"""
Strategic Business Plan Service
Handles CRUD and business logic for Strategic Business Plan projects
"""
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone

from app.models.strategic_business_plan import StrategicBusinessPlan
from app.models.diagnostic import Diagnostic
import logging

logger = logging.getLogger(__name__)

# Default section structure initialised when drafting begins
DEFAULT_SECTIONS = [
    {"key": "executive_summary", "title": "Executive Summary"},
    {"key": "strategic_intent", "title": "Strategic Intent Overview"},
    {"key": "business_context", "title": "Business and Context Overview"},
    {"key": "external_internal_analysis", "title": "External and Internal Analysis"},
    {"key": "growth_opportunities", "title": "Growth Opportunities and Strategic Direction"},
    {"key": "functional_strategies", "title": "Functional and Thematic Strategies"},
    {"key": "financial_overview", "title": "Financial Overview"},
    {"key": "strategic_priorities", "title": "Strategic Priorities and Key Initiatives"},
    {"key": "implementation_roadmap", "title": "Implementation Roadmap"},
    {"key": "risk_matrix", "title": "Risk Matrix and Mitigation"},
    {"key": "actions_next_steps", "title": "Actions List and Next Steps"},
    {"key": "strategic_alignment", "title": "Integrated Strategic Implications & Alignment"},
    {"key": "appendices", "title": "Appendices"},
]


def _blank_section(template: dict) -> dict:
    """Return a section dict with default fields populated."""
    return {
        "key": template["key"],
        "title": template["title"],
        "status": "pending",
        "content": None,
        "strategic_implications": None,
        "revision_notes": None,
        "revision_history": [],
        "approved_at": None,
        "draft_count": 0,
    }


class SBPService:
    """Service for managing Strategic Business Plan projects"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_plan(self, user_id: UUID, engagement_id: Optional[UUID] = None) -> StrategicBusinessPlan:
        plan = StrategicBusinessPlan(
            created_by_user_id=user_id,
            engagement_id=engagement_id,
            status="draft",
            current_step=1,
            max_step_reached=1,
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        logger.info(f"Created SBP {plan.id} for user {user_id}")
        return plan

    def create_plan_from_diagnostic(self, diagnostic_id: UUID, user_id: UUID) -> StrategicBusinessPlan:
        diagnostic = self.db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
        if not diagnostic:
            raise ValueError(f"Diagnostic {diagnostic_id} not found")
        if diagnostic.status != "completed":
            raise ValueError(f"Diagnostic must be completed (current status: {diagnostic.status})")

        # Check for existing plan linked to this diagnostic
        existing = self.get_plan_by_diagnostic(diagnostic_id)
        if existing:
            logger.info(f"SBP already exists for diagnostic {diagnostic_id}: {existing.id}")
            return existing

        diagnostic_context = {}
        if diagnostic.report_html:
            diagnostic_context["report_html"] = diagnostic.report_html
        if diagnostic.ai_analysis:
            diagnostic_context["ai_analysis"] = diagnostic.ai_analysis

        plan = StrategicBusinessPlan(
            created_by_user_id=user_id,
            engagement_id=diagnostic.engagement_id,
            diagnostic_id=diagnostic_id,
            diagnostic_context=diagnostic_context or None,
            status="draft",
            current_step=1,
            max_step_reached=1,
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        logger.info(f"Created SBP {plan.id} from diagnostic {diagnostic_id}")
        return plan

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_plan(self, plan_id: UUID) -> Optional[StrategicBusinessPlan]:
        return self.db.query(StrategicBusinessPlan).filter(StrategicBusinessPlan.id == plan_id).first()

    def get_plan_by_diagnostic(self, diagnostic_id: UUID) -> Optional[StrategicBusinessPlan]:
        return (
            self.db.query(StrategicBusinessPlan)
            .filter(StrategicBusinessPlan.diagnostic_id == diagnostic_id)
            .first()
        )

    def get_plans_by_engagement(self, engagement_id: UUID, user_id: Optional[UUID] = None) -> List[StrategicBusinessPlan]:
        query = self.db.query(StrategicBusinessPlan).filter(
            StrategicBusinessPlan.engagement_id == engagement_id
        )
        if user_id:
            query = query.filter(StrategicBusinessPlan.created_by_user_id == user_id)
        return query.order_by(StrategicBusinessPlan.updated_at.desc()).all()

    # ------------------------------------------------------------------
    # Step 1: Setup
    # ------------------------------------------------------------------

    def save_setup(self, plan_id: UUID, client_name: str, industry: str,
                   planning_horizon: str, target_audience: str,
                   additional_context: Optional[str] = None) -> StrategicBusinessPlan:
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan.client_name = client_name
        plan.industry = industry
        plan.planning_horizon = planning_horizon
        plan.target_audience = target_audience
        plan.additional_context = additional_context
        plan.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(plan)
        return plan

    def save_file_upload(self, plan_id: UUID, file_ids: list, file_mappings: dict,
                         stored_files: Optional[dict] = None) -> StrategicBusinessPlan:
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan.file_ids = file_ids
        plan.file_mappings = file_mappings
        if stored_files:
            plan.stored_files = stored_files
        plan.status = "uploading"
        plan.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(plan)
        return plan

    def reset_plan_data(self, plan_id: UUID) -> StrategicBusinessPlan:
        """Clear all generated data so the plan can be restarted from step 1."""
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan.file_ids = None
        plan.file_mappings = None
        plan.file_tags = None
        plan.stored_files = None
        plan.cross_analysis = None
        plan.cross_analysis_advisor_notes = None
        plan.sections = None
        plan.current_section_index = None
        plan.emerging_themes = None
        plan.final_plan = None
        plan.generated_report_path = None
        plan.presentation_slides = None
        plan.status = "draft"
        plan.current_step = 1
        plan.max_step_reached = 1
        plan.completed_at = None
        plan.updated_at = datetime.now(timezone.utc)

        flag_modified(plan, "file_ids")
        flag_modified(plan, "file_mappings")
        flag_modified(plan, "cross_analysis")
        flag_modified(plan, "sections")
        flag_modified(plan, "emerging_themes")
        flag_modified(plan, "final_plan")
        flag_modified(plan, "presentation_slides")

        self.db.commit()
        self.db.refresh(plan)
        logger.info(f"Reset SBP {plan_id} data for restart")
        return plan

    # ------------------------------------------------------------------
    # Step 2: Cross-Analysis
    # ------------------------------------------------------------------

    def save_cross_analysis(self, plan_id: UUID, cross_analysis: dict) -> StrategicBusinessPlan:
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan.cross_analysis = cross_analysis
        plan.status = "analysing"
        plan.updated_at = datetime.now(timezone.utc)
        flag_modified(plan, "cross_analysis")

        self.db.commit()
        self.db.refresh(plan)
        return plan

    def save_cross_analysis_notes(self, plan_id: UUID, notes: str) -> StrategicBusinessPlan:
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan.cross_analysis_advisor_notes = notes
        plan.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(plan)
        return plan

    # ------------------------------------------------------------------
    # Step 3: Section Drafting
    # ------------------------------------------------------------------

    def initialise_sections(self, plan_id: UUID) -> StrategicBusinessPlan:
        """Initialise the sections array with blank entries for all 13 sections."""
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan.sections = [_blank_section(s) for s in DEFAULT_SECTIONS]
        plan.current_section_index = 0
        plan.status = "drafting"
        plan.updated_at = datetime.now(timezone.utc)
        flag_modified(plan, "sections")

        self.db.commit()
        self.db.refresh(plan)
        return plan

    def update_section(self, plan_id: UUID, section_key: str, updates: dict) -> StrategicBusinessPlan:
        """Update a specific section's fields."""
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        if not plan.sections:
            raise ValueError("Sections not initialised")

        sections = list(plan.sections)
        for i, section in enumerate(sections):
            if section["key"] == section_key:
                sections[i] = {**section, **updates}
                break
        else:
            raise ValueError(f"Section '{section_key}' not found")

        plan.sections = sections
        plan.updated_at = datetime.now(timezone.utc)
        flag_modified(plan, "sections")

        self.db.commit()
        self.db.refresh(plan)
        return plan

    def approve_section(self, plan_id: UUID, section_key: str) -> StrategicBusinessPlan:
        return self.update_section(plan_id, section_key, {
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "revision_notes": None,
        })

    def save_emerging_themes(self, plan_id: UUID, themes: dict) -> StrategicBusinessPlan:
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan.emerging_themes = themes
        plan.updated_at = datetime.now(timezone.utc)
        flag_modified(plan, "emerging_themes")

        self.db.commit()
        self.db.refresh(plan)
        return plan

    def update_current_section_index(self, plan_id: UUID, index: int) -> StrategicBusinessPlan:
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan.current_section_index = index
        plan.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(plan)
        return plan

    # ------------------------------------------------------------------
    # Step 4: Plan Assembly
    # ------------------------------------------------------------------

    def assemble_final_plan(self, plan_id: UUID, section_order: Optional[List[str]] = None) -> StrategicBusinessPlan:
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        if not plan.sections:
            raise ValueError("Sections not initialised")

        sections = list(plan.sections)
        if section_order:
            ordered = []
            key_map = {s["key"]: s for s in sections}
            for key in section_order:
                if key in key_map:
                    ordered.append(key_map[key])
            # Append any remaining sections not in the custom order
            for s in sections:
                if s["key"] not in section_order:
                    ordered.append(s)
            sections = ordered

        plan.final_plan = {
            "sections": sections,
            "client_name": plan.client_name,
            "industry": plan.industry,
            "planning_horizon": plan.planning_horizon,
            "target_audience": plan.target_audience,
            "assembled_at": datetime.now(timezone.utc).isoformat(),
        }
        plan.status = "reviewing"
        plan.updated_at = datetime.now(timezone.utc)
        flag_modified(plan, "final_plan")

        self.db.commit()
        self.db.refresh(plan)
        return plan

    # ------------------------------------------------------------------
    # Step tracking
    # ------------------------------------------------------------------

    def update_step_progress(self, plan_id: UUID, current_step: Optional[int] = None,
                              max_step_reached: Optional[int] = None) -> StrategicBusinessPlan:
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        if current_step is not None:
            plan.current_step = current_step
        if max_step_reached is not None:
            plan.max_step_reached = max(max_step_reached, plan.max_step_reached or 0)
        plan.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(plan)
        return plan

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def mark_completed(self, plan_id: UUID) -> StrategicBusinessPlan:
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan.status = "completed"
        plan.completed_at = datetime.now(timezone.utc)
        plan.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(plan)
        return plan


def get_sbp_service(db: Session) -> SBPService:
    """Factory function for dependency injection"""
    return SBPService(db)
