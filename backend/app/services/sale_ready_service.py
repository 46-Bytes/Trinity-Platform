"""
Sale Ready Program service.

Owns:
  - Task auto-generation into the existing task system on engagement creation
    (idempotent), plus seeding stage state and DD items.
  - The composed roadmap / stage view (templates + per-engagement state).
  - Persisted module ordering (advisor-set, with an "apply recommended order"
    action that reuses the Program Guide BBA-findings computation).
  - Stage-state, DD-item, and document-register mutations.

The DD checklist is one table (``engagement_dd_item``) viewed two ways: the
master view is all rows for the engagement; a module view is the same rows
filtered by ``module_code``. There is no sync - it's a WHERE clause.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.engagement import Engagement
from app.models.task import Task
from app.models.user import User
from app.models.sale_ready import (
    ProgramStage,
    ProgramTaskTemplate,
    ProgramDDTemplate,
    EngagementStageState,
    EngagementDDItem,
    EngagementDocumentRegisterEntry,
)
from app.services.program_guide_service import ProgramGuideService

PROGRAM_TYPE = "sale_ready"
GENERATED_TASK_TYPE = "sale_ready_generated"


class SaleReadyService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------
    def _stages(self) -> List[ProgramStage]:
        return (
            self.db.query(ProgramStage)
            .filter(ProgramStage.program_type == PROGRAM_TYPE, ProgramStage.is_active == True)  # noqa: E712
            .order_by(ProgramStage.default_order.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # Generation (idempotent)
    # ------------------------------------------------------------------
    def has_generated(self, engagement_id: UUID) -> bool:
        return (
            self.db.query(EngagementStageState.id)
            .filter(EngagementStageState.engagement_id == engagement_id)
            .first()
            is not None
        )

    def generate_engagement(self, engagement: Engagement, created_by_user_id: UUID) -> Dict[str, Any]:
        """
        Seed stage state, generate tasks into the existing task system, and seed
        DD items - all in one transaction. Idempotent: a no-op if this engagement
        already has stage state (guards against a double-fired creation hook).

        Module ordering is intentionally NOT set here - priority_order stays NULL
        until the advisor applies/adjusts it at the Prioritisation stage.
        """
        if self.has_generated(engagement.id):
            return {"generated": False, "reason": "already_generated"}

        stages = self._stages()
        if not stages:
            return {"generated": False, "reason": "no_templates"}

        stage_codes = [s.stage_code for s in stages]
        assignee = [engagement.primary_advisor_id] if engagement.primary_advisor_id else None
        today = date.today()

        # 1) Seed stage state (not_started, no priority_order yet).
        for s in stages:
            self.db.add(EngagementStageState(
                engagement_id=engagement.id,
                stage_code=s.stage_code,
                status="not_started",
            ))

        # 2) Generate tasks into the existing tasks table, tagged stage + section.
        task_templates = (
            self.db.query(ProgramTaskTemplate)
            .filter(
                ProgramTaskTemplate.program_type == PROGRAM_TYPE,
                ProgramTaskTemplate.is_active == True,  # noqa: E712
                ProgramTaskTemplate.stage_code.in_(stage_codes),
            )
            .order_by(ProgramTaskTemplate.default_order.asc())
            .all()
        )
        task_count = 0
        for t in task_templates:
            due = today + timedelta(days=t.due_offset_days) if t.due_offset_days is not None else None
            self.db.add(Task(
                engagement_id=engagement.id,
                created_by_user_id=created_by_user_id,
                assigned_to_user_ids=assignee,
                title=t.title,
                description=t.description,
                task_type=GENERATED_TASK_TYPE,
                status="pending",
                priority=t.priority or "medium",
                module_reference=t.stage_code,
                section=t.section,
                due_date=due,
            ))
            task_count += 1

        # 3) Seed DD items from templates.
        dd_templates = (
            self.db.query(ProgramDDTemplate)
            .filter(
                ProgramDDTemplate.program_type == PROGRAM_TYPE,
                ProgramDDTemplate.is_active == True,  # noqa: E712
            )
            .order_by(ProgramDDTemplate.default_order.asc())
            .all()
        )
        dd_count = 0
        for d in dd_templates:
            self.db.add(EngagementDDItem(
                engagement_id=engagement.id,
                module_code=d.module_code,
                category=d.category,
                sub_item=d.sub_item,
                document_required=d.document_required,
                action_step=d.action_step,
                display_order=d.default_order,
            ))
            dd_count += 1

        self.db.commit()
        return {
            "generated": True,
            "stages": len(stages),
            "tasks": task_count,
            "dd_items": dd_count,
        }

    # ------------------------------------------------------------------
    # Members (assignable people on the engagement)
    # ------------------------------------------------------------------
    def list_members(self, engagement: Engagement) -> List[Dict[str, Any]]:
        """Advisors + clients on the engagement, for lead-advisor / responsible-person pickers."""
        ordered_ids: List[Any] = []
        if engagement.primary_advisor_id:
            ordered_ids.append(engagement.primary_advisor_id)
        for a in (engagement.secondary_advisor_ids or []):
            ordered_ids.append(a)
        client_ids = engagement.client_ids or ([engagement.client_id] if engagement.client_id else [])
        for c in client_ids:
            ordered_ids.append(c)

        # De-dupe while preserving order.
        seen: set = set()
        ids = [i for i in ordered_ids if not (i in seen or seen.add(i))]
        if not ids:
            return []

        users = {u.id: u for u in self.db.query(User).filter(User.id.in_(ids)).all()}
        result: List[Dict[str, Any]] = []
        for i in ids:
            u = users.get(i)
            if not u:
                continue
            role = getattr(u.role, "value", None) or str(u.role) if u.role is not None else None
            result.append({
                "id": str(u.id),
                "name": u.name or u.email or u.nickname,
                "role": role,
            })
        return result

    # ------------------------------------------------------------------
    # Composed roadmap / stage view
    # ------------------------------------------------------------------
    def _state_map(self, engagement_id: UUID) -> Dict[str, EngagementStageState]:
        rows = (
            self.db.query(EngagementStageState)
            .filter(EngagementStageState.engagement_id == engagement_id)
            .all()
        )
        return {r.stage_code: r for r in rows}

    def get_stages_view(self, engagement: Engagement) -> Dict[str, Any]:
        """
        All stages composed with per-engagement state, in workflow order:
        pre-module (by default_order) -> modules (by priority_order, falling back
        to default_order) -> post-module (by default_order).
        """
        stages = self._stages()
        states = self._state_map(engagement.id)

        def compose(s: ProgramStage) -> Dict[str, Any]:
            st = states.get(s.stage_code)
            return {
                **s.to_dict(),
                "status": st.status if st else "not_started",
                "start_date": st.start_date.isoformat() if st and st.start_date else None,
                "due_date": st.due_date.isoformat() if st and st.due_date else None,
                "lead_advisor_id": str(st.lead_advisor_id) if st and st.lead_advisor_id else None,
                "priority_order": st.priority_order if st else None,
            }

        composed = [compose(s) for s in stages]

        def sort_key(m: Dict[str, Any]):
            group = {"pre_module": 0, "module": 1, "post_module": 2}.get(m["stage_type"], 1)
            if m["stage_type"] == "module":
                order = m["priority_order"] if m["priority_order"] is not None else m["default_order"]
            else:
                order = m["default_order"]
            return (group, order)

        composed.sort(key=sort_key)
        return {"program_type": PROGRAM_TYPE, "stages": composed}

    def get_roadmap(self, engagement: Engagement) -> Dict[str, Any]:
        """Modules only, in effective priority order, with status - for the Roadmap dashboard."""
        view = self.get_stages_view(engagement)
        modules = [m for m in view["stages"] if m["stage_type"] == "module"]
        return {"program_type": PROGRAM_TYPE, "modules": modules}

    # ------------------------------------------------------------------
    # Ordering
    # ------------------------------------------------------------------
    def compute_recommended_order(self, engagement: Engagement) -> Dict[str, Any]:
        """
        Recommended module order from the latest BBA ("Recommendations Report
        Builder") findings, reusing the Program Guide matcher. Returns all module
        stage_codes; modules BBA didn't rank are appended in default order.
        """
        module_stages = [s for s in self._stages() if s.stage_type == "module"]
        canonical = {s.stage_code: s.title for s in module_stages}
        all_codes = [s.stage_code for s in module_stages]

        guide = ProgramGuideService(self.db)
        bba = guide._get_latest_bba_with_findings(engagement.id)
        if not bba:
            return {"source": "default", "order": all_codes, "bba_id": None, "unmapped_priority_areas": []}

        findings = sorted(
            (bba.draft_findings or {}).get("findings", []) or [],
            key=lambda f: f.get("rank", 999),
        )
        matched: List[str] = []
        seen: set = set()
        unmapped: List[str] = []
        for finding in findings:
            raw_area = finding.get("priority_area")
            code = ProgramGuideService._match_priority_area_to_module(raw_area, canonical)
            if code and code not in seen:
                matched.append(code)
                seen.add(code)
            elif not code and raw_area:
                unmapped.append(raw_area)

        remaining = [c for c in all_codes if c not in seen]
        return {"source": "bba", "order": matched + remaining, "bba_id": str(bba.id), "unmapped_priority_areas": unmapped}

    def _write_priority_order(self, engagement_id: UUID, ordered_codes: List[str]) -> None:
        states = self._state_map(engagement_id)
        for idx, code in enumerate(ordered_codes):
            st = states.get(code)
            if st:
                st.priority_order = idx + 1
        self.db.commit()

    def apply_recommended_order(self, engagement: Engagement) -> Dict[str, Any]:
        """One-time event: compute recommended order and persist it into priority_order."""
        rec = self.compute_recommended_order(engagement)
        self._write_priority_order(engagement.id, rec["order"])
        return self.get_roadmap(engagement)

    def set_module_order(self, engagement: Engagement, ordered_codes: List[str]) -> Dict[str, Any]:
        """Persist an advisor-set module order (drag/drop or manual numbering)."""
        self._write_priority_order(engagement.id, ordered_codes)
        return self.get_roadmap(engagement)

    # ------------------------------------------------------------------
    # Stage state
    # ------------------------------------------------------------------
    def _get_state(self, engagement_id: UUID, stage_code: str) -> Optional[EngagementStageState]:
        return (
            self.db.query(EngagementStageState)
            .filter(
                EngagementStageState.engagement_id == engagement_id,
                EngagementStageState.stage_code == stage_code,
            )
            .first()
        )

    def update_stage_state(self, engagement_id: UUID, stage_code: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        st = self._get_state(engagement_id, stage_code)
        if st is None:
            st = EngagementStageState(engagement_id=engagement_id, stage_code=stage_code)
            self.db.add(st)
        for field in ("status", "start_date", "due_date", "lead_advisor_id"):
            if field in updates:
                setattr(st, field, updates[field])
        self.db.commit()
        self.db.refresh(st)
        return st.to_dict()

    def stage_task_completion(self, engagement_id: UUID, stage_code: str) -> Dict[str, int]:
        """Task counts for a stage - powers the 'all tasks done -> mark Complete?' nudge."""
        rows = (
            self.db.query(Task)
            .filter(
                Task.engagement_id == engagement_id,
                Task.module_reference == stage_code,
                Task.is_deleted == False,  # noqa: E712
            )
            .all()
        )
        total = len(rows)
        done = sum(1 for t in rows if t.status == "completed")
        return {"total": total, "completed": done}

    # ------------------------------------------------------------------
    # DD items - single source of truth for master + module views
    # ------------------------------------------------------------------
    def list_dd_items(
        self,
        engagement_id: UUID,
        module_code: Optional[str] = None,
        category: Optional[str] = None,
        completed: Optional[bool] = None,
        responsible_user_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        q = self.db.query(EngagementDDItem).filter(EngagementDDItem.engagement_id == engagement_id)
        if module_code:
            q = q.filter(EngagementDDItem.module_code == module_code)
        if category:
            q = q.filter(EngagementDDItem.category == category)
        if completed is not None:
            q = q.filter(EngagementDDItem.completed == completed)
        if responsible_user_id:
            q = q.filter(EngagementDDItem.responsible_user_id == responsible_user_id)
        rows = q.order_by(EngagementDDItem.module_code.asc(), EngagementDDItem.display_order.asc()).all()
        return [r.to_dict() for r in rows]

    def create_dd_item(self, engagement_id: UUID, data: Dict[str, Any]) -> Dict[str, Any]:
        item = EngagementDDItem(engagement_id=engagement_id, **data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item.to_dict()

    def update_dd_item(self, engagement_id: UUID, item_id: UUID, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        item = (
            self.db.query(EngagementDDItem)
            .filter(EngagementDDItem.id == item_id, EngagementDDItem.engagement_id == engagement_id)
            .first()
        )
        if item is None:
            return None
        # Keep date_completed in sync with the completed flag unless explicitly provided.
        if "completed" in updates and "date_completed" not in updates:
            updates["date_completed"] = date.today() if updates["completed"] else None
        for field, value in updates.items():
            setattr(item, field, value)
        self.db.commit()
        self.db.refresh(item)
        return item.to_dict()

    def delete_dd_item(self, engagement_id: UUID, item_id: UUID) -> bool:
        item = (
            self.db.query(EngagementDDItem)
            .filter(EngagementDDItem.id == item_id, EngagementDDItem.engagement_id == engagement_id)
            .first()
        )
        if item is None:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Document register
    # ------------------------------------------------------------------
    def list_documents(self, engagement_id: UUID, stage_code: Optional[str] = None) -> List[Dict[str, Any]]:
        q = self.db.query(EngagementDocumentRegisterEntry).filter(
            EngagementDocumentRegisterEntry.engagement_id == engagement_id
        )
        if stage_code:
            q = q.filter(EngagementDocumentRegisterEntry.stage_code == stage_code)
        rows = q.order_by(EngagementDocumentRegisterEntry.created_at.asc()).all()
        return [r.to_dict() for r in rows]

    def create_document(self, engagement_id: UUID, data: Dict[str, Any]) -> Dict[str, Any]:
        entry = EngagementDocumentRegisterEntry(engagement_id=engagement_id, **data)
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry.to_dict()

    def update_document(self, engagement_id: UUID, entry_id: UUID, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        entry = (
            self.db.query(EngagementDocumentRegisterEntry)
            .filter(
                EngagementDocumentRegisterEntry.id == entry_id,
                EngagementDocumentRegisterEntry.engagement_id == engagement_id,
            )
            .first()
        )
        if entry is None:
            return None
        for field, value in updates.items():
            setattr(entry, field, value)
        self.db.commit()
        self.db.refresh(entry)
        return entry.to_dict()

    def delete_document(self, engagement_id: UUID, entry_id: UUID) -> bool:
        entry = (
            self.db.query(EngagementDocumentRegisterEntry)
            .filter(
                EngagementDocumentRegisterEntry.id == entry_id,
                EngagementDocumentRegisterEntry.engagement_id == engagement_id,
            )
            .first()
        )
        if entry is None:
            return False
        self.db.delete(entry)
        self.db.commit()
        return True


def get_sale_ready_service(db: Session) -> SaleReadyService:
    return SaleReadyService(db)
