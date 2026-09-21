"""
Sale Ready service: per-engagement stages, tasks and due diligence (DD) items.

Sale Ready runs on stages + tasks + DD items, not on Program Guide deliverables.
Templates are seeded by scripts/seed_sale_ready_program.py; this service copies
them onto an engagement and applies the rules in sale_ready_rules.

Initialization is lazy and idempotent (ensure_initialized): the first read
creates the stage rows, the 210 DD items, and the tasks of every stage created
with the engagement. Existing Sale Ready engagements are initialized the same way.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.engagement import Engagement
from app.models.sale_ready import (
    EngagementDDItem,
    EngagementProgramCloseout,
    EngagementSalePlanner,
    EngagementStageState,
    ProgramDDTemplate,
    ProgramStage,
    ProgramTaskTemplate,
)
from app.models.task import Task
from app.models.user import User, UserRole
from app.services import sale_ready_rules as rules
from app.services.program_guide_service import get_program_guide_service
from app.services.program_registry import PROGRAM_SALE_READY, pinned_last_modules

logger = logging.getLogger(__name__)

TASK_CREATION_ON_ENGAGEMENT = "on_engagement_create"
TASK_CREATION_ON_START = "on_start"
# Existing Task.status values; Sale Ready adds none (C7 is still open).
TASK_STATUSES = frozenset({"pending", "in_progress", "completed", "cancelled"})
SECTION_ORDER = {rules.SECTION_MUST_DO: 0, rules.SECTION_OPTIONAL: 1, rules.SECTION_CLIENT_SPECIFIC: 2}


class SaleReadyNotFound(LookupError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _display_name(user: User) -> str:
    full = " ".join(p for p in (user.first_name, user.last_name) if p)
    return user.name or full or user.email


def _role_value(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


class SaleReadyService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------
    def _stages(self) -> List[ProgramStage]:
        return (
            self.db.query(ProgramStage)
            .filter(ProgramStage.program_type == PROGRAM_SALE_READY, ProgramStage.is_active == True)  # noqa: E712
            .order_by(ProgramStage.default_order.asc())
            .all()
        )

    def _stage_or_404(self, stage_code: str) -> ProgramStage:
        stage = next((s for s in self._stages() if s.stage_code == stage_code), None)
        if not stage:
            raise SaleReadyNotFound(f"Stage {stage_code} not found")
        return stage

    def _task_templates(self, stage_code: Optional[str] = None) -> List[ProgramTaskTemplate]:
        query = self.db.query(ProgramTaskTemplate).filter(
            ProgramTaskTemplate.program_type == PROGRAM_SALE_READY,
            ProgramTaskTemplate.is_active == True,  # noqa: E712
        )
        if stage_code:
            query = query.filter(ProgramTaskTemplate.stage_code == stage_code)
        return query.order_by(ProgramTaskTemplate.default_order.asc()).all()

    # ------------------------------------------------------------------
    # Engagement state
    # ------------------------------------------------------------------
    def _states(self, engagement_id: UUID) -> Dict[str, EngagementStageState]:
        rows = self.db.query(EngagementStageState).filter(EngagementStageState.engagement_id == engagement_id).all()
        return {r.stage_code: r for r in rows}

    def _state_or_404(self, engagement: Engagement, stage_code: str, actor: User) -> EngagementStageState:
        self.ensure_initialized(engagement, actor)
        state = self._states(engagement.id).get(stage_code)
        if not state:
            raise SaleReadyNotFound(f"Stage {stage_code} not found")
        return state

    def _tasks(self, engagement_id: UUID, stage_code: Optional[str] = None) -> List[Task]:
        """Live Sale Ready tasks: those with a section. Other engagement tasks are left alone."""
        query = self.db.query(Task).filter(
            Task.engagement_id == engagement_id,
            Task.is_deleted == False,  # noqa: E712
            Task.section.isnot(None),
        )
        if stage_code:
            query = query.filter(Task.module_reference == stage_code)
        return query.order_by(Task.created_at.asc()).all()

    def _dd_items(self, engagement_id: UUID, stage_code: Optional[str] = None) -> List[EngagementDDItem]:
        query = self.db.query(EngagementDDItem).filter(EngagementDDItem.engagement_id == engagement_id)
        if stage_code:
            query = query.filter(EngagementDDItem.stage_code == stage_code)
        return query.order_by(EngagementDDItem.display_order.asc()).all()

    def _creator_id(self, engagement: Engagement, actor: Optional[User]) -> Optional[UUID]:
        return engagement.primary_advisor_id or (actor.id if actor else None)

    def _create_template_tasks(
        self, engagement: Engagement, stage_code: str, state: EngagementStageState, creator_id: UUID
    ) -> int:
        """Copy the stage's task templates into `tasks`; skips templates that already have a live task."""
        existing = {
            t.source_task_template_id
            for t in self._tasks(engagement.id, stage_code)
            if t.source_task_template_id
        }
        # Must-do tasks default to the stage lead, else the engagement's primary advisor.
        lead = state.lead_advisor_id or engagement.primary_advisor_id
        created = 0
        for template in self._task_templates(stage_code):
            if template.id in existing:
                continue
            due = None
            if state.start_date and template.due_offset_days is not None:
                due = state.start_date + timedelta(days=template.due_offset_days)
            self.db.add(Task(
                engagement_id=engagement.id,
                created_by_user_id=creator_id,
                title=template.title,
                description=template.description,
                task_type="manual",
                status=rules.TASK_STATUS_PENDING,
                priority=template.priority or "medium",
                module_reference=stage_code,
                section=template.section,
                source_task_template_id=template.id,
                assigned_to_user_ids=[lead] if lead and template.section == rules.SECTION_MUST_DO else None,
                due_date=due,
            ))
            created += 1
        return created

    def ensure_initialized(self, engagement: Engagement, actor: Optional[User] = None) -> None:
        """
        Create what the engagement is missing: stage rows, DD items, and the tasks
        of stages created with the engagement. Tasks are only created alongside a
        NEW stage row, so a task an advisor deletes is not recreated on the next read.
        """
        states = self._states(engagement.id)
        dd_template_ids = {
            row[0] for row in self.db.query(EngagementDDItem.template_item_id)
            .filter(EngagementDDItem.engagement_id == engagement.id)
        }
        creator_id = self._creator_id(engagement, actor)
        changed = False

        for stage in self._stages():
            if stage.stage_code in states:
                continue
            state = EngagementStageState(
                engagement_id=engagement.id,
                stage_code=stage.stage_code,
                status=rules.STAGE_STATE_NOT_STARTED,
            )
            self.db.add(state)
            if stage.task_creation == TASK_CREATION_ON_ENGAGEMENT and creator_id:
                self._create_template_tasks(engagement, stage.stage_code, state, creator_id)
            changed = True

        dd_templates = (
            self.db.query(ProgramDDTemplate)
            .filter(ProgramDDTemplate.program_type == PROGRAM_SALE_READY, ProgramDDTemplate.is_active == True)  # noqa: E712
            .order_by(ProgramDDTemplate.default_order.asc())
            .all()
        )
        for t in dd_templates:
            if t.id in dd_template_ids:
                continue
            self.db.add(EngagementDDItem(
                engagement_id=engagement.id,
                template_item_id=t.id,
                item_key=t.item_key,
                stage_code=t.stage_code,
                category_code=t.category_code,
                category=t.category,
                sub_item_code=t.sub_item_code,
                sub_item=t.sub_item,
                document_required=t.document_required,
                action_step=t.action_step,
                display_order=t.default_order,
            ))
            changed = True

        if not changed:
            return
        try:
            self.db.commit()
        except IntegrityError:
            # A concurrent first read initialized it; the unique constraints kept one copy.
            self.db.rollback()
            logger.info("Sale Ready initialization for engagement %s raced; using existing rows", engagement.id)

    # ------------------------------------------------------------------
    # People
    # ------------------------------------------------------------------
    def people(self, engagement: Engagement) -> List[Dict[str, Any]]:
        ids: List[UUID] = []
        for uid in [engagement.primary_advisor_id, *(engagement.secondary_advisor_ids or []),
                    engagement.client_id, *(engagement.client_ids or [])]:
            if uid and uid not in ids:
                ids.append(uid)
        if not ids:
            return []
        users = self.db.query(User).filter(
            User.id.in_(ids), User.is_deleted == False, User.is_active == True,  # noqa: E712
        ).all()
        by_id = {u.id: u for u in users}
        return [
            {"id": by_id[i].id, "name": _display_name(by_id[i]), "role": _role_value(by_id[i])}
            for i in ids if i in by_id
        ]

    def _validate_member(self, engagement: Engagement, user_id: Optional[UUID], advisors_only: bool = False) -> None:
        if user_id is None:
            return
        for person in self.people(engagement):
            if person["id"] == user_id:
                if advisors_only and person["role"] == UserRole.CLIENT.value:
                    raise ValueError("The lead advisor must be an advisor on this engagement")
                return
        raise ValueError("That person is not a member of this engagement")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def _summaries(self, engagement: Engagement) -> Tuple[Dict[str, Dict[str, Any]], str]:
        """Derived status and counts for every stage keyed by stage code, and the order source."""
        states = self._states(engagement.id)
        tasks_by_stage: Dict[str, List[Task]] = {}
        for t in self._tasks(engagement.id):
            tasks_by_stage.setdefault(t.module_reference, []).append(t)
        dd_by_stage: Dict[str, List[EngagementDDItem]] = {}
        for d in self._dd_items(engagement.id):
            dd_by_stage.setdefault(d.stage_code, []).append(d)
        must_templates: Dict[str, int] = {}
        for t in self._task_templates():
            if t.section == rules.SECTION_MUST_DO:
                must_templates[t.stage_code] = must_templates.get(t.stage_code, 0) + 1

        pinned = pinned_last_modules(PROGRAM_SALE_READY)
        effective = get_program_guide_service(self.db).get_effective_order(engagement)
        rank = {code: i + 1 for i, code in enumerate(effective["order"])}

        out = {}
        for stage in self._stages():
            state = states.get(stage.stage_code)
            stored = state.status if state else rules.STAGE_STATE_NOT_STARTED
            tasks = tasks_by_stage.get(stage.stage_code, [])
            dd = dd_by_stage.get(stage.stage_code, [])
            snapshots = [rules.TaskSnapshot(t.section, t.status, t.sale_ready_state) for t in tasks]
            dd_statuses = [d.status for d in dd]
            tasks_created = (
                stage.task_creation == TASK_CREATION_ON_ENGAGEMENT
                or stored != rules.STAGE_STATE_NOT_STARTED
                or any(t.source_task_template_id for t in tasks)
            )
            must = [t for t in tasks if t.section == rules.SECTION_MUST_DO]
            is_module = stage.stage_type == rules.STAGE_TYPE_MODULE
            out[stage.stage_code] = {
                "stage": stage,
                "state": state,
                "tasks": tasks,
                "dd": dd,
                "snapshots": snapshots,
                "dd_statuses": dd_statuses,
                "summary": {
                    "stage_code": stage.stage_code,
                    "display_code": stage.display_code,
                    "title": stage.title,
                    "stage_type": stage.stage_type,
                    "ui_variant": stage.ui_variant,
                    "status": rules.derive_stage_status(stored, snapshots, dd_statuses),
                    "effective_rank": rank.get(stage.stage_code) if is_module else None,
                    "is_pinned_last": is_module and stage.stage_code in pinned,
                    "tasks_created": tasks_created,
                    # Before tasks exist, the total is what starting would create.
                    "must_do_total": len(must) if tasks_created else must_templates.get(stage.stage_code, 0),
                    "must_do_resolved": sum(
                        1 for t in must
                        if rules.is_task_resolved(rules.TaskSnapshot(t.section, t.status, t.sale_ready_state))
                    ),
                    "dd_total": len(dd),
                    "dd_yes": sum(1 for s in dd_statuses if s == rules.DD_STATUS_YES),
                    "start_date": state.start_date if state else None,
                    "due_date": state.due_date if state else None,
                },
            }
        return out, effective["source"]

    # ------------------------------------------------------------------
    # Roadmap
    # ------------------------------------------------------------------
    def get_roadmap(self, engagement: Engagement, actor: Optional[User] = None) -> Dict[str, Any]:
        self.ensure_initialized(engagement, actor)
        summaries, order_source = self._summaries(engagement)
        items = [s["summary"] for s in summaries.values()]

        modules = [i for i in items if i["stage_type"] == rules.STAGE_TYPE_MODULE]
        modules.sort(key=lambda m: (m["effective_rank"] is None, m["effective_rank"] or 0))

        progress = rules.program_progress([
            rules.StageProgress(i["stage_type"], i["status"], i["must_do_total"], i["must_do_resolved"],
                                i["dd_total"], i["dd_yes"])
            for i in items
        ])
        all_dd = [d for s in summaries.values() for d in s["dd"]]
        gaps = rules.summarise_gaps((d.status, d.gap_handling) for d in all_dd)

        lead = None
        if engagement.primary_advisor_id:
            user = self.db.query(User).filter(User.id == engagement.primary_advisor_id).first()
            lead = _display_name(user) if user else None

        closeout = self.db.query(EngagementProgramCloseout).filter(
            EngagementProgramCloseout.engagement_id == engagement.id
        ).first()
        planner = self.db.query(EngagementSalePlanner).filter(
            EngagementSalePlanner.engagement_id == engagement.id
        ).first()
        planner_stage = summaries.get("SALE_PLANNER", {}).get("stage")
        issues_total = len(((planner_stage.ui_config if planner_stage else None) or {}).get("issues", []))

        return {
            "engagement_id": engagement.id,
            "order_source": order_source,
            "phases": [i for i in items if i["stage_type"] == rules.STAGE_TYPE_PRE_MODULE],
            "modules": modules,
            "post_phases": [i for i in items if i["stage_type"] == rules.STAGE_TYPE_POST_MODULE],
            "progress": progress._asdict(),
            "gaps": gaps._asdict(),
            "lead_advisor_name": lead,
            "closeout": {
                "is_closed": bool(closeout and closeout.closed_at),
                "closed_at": closeout.closed_at if closeout else None,
                "referred_to_benchmark": bool(closeout and closeout.referred_to_benchmark),
            },
            "sale_planner_issues": {
                "addressed": sum(1 for v in (planner.issues if planner else {}).values() if v.get("addressed")),
                "total": issues_total,
            },
        }

    # ------------------------------------------------------------------
    # Module order - stored by the Program Guide's order state, M8 pinned last
    # ------------------------------------------------------------------
    def set_module_order(self, engagement: Engagement, order: List[str], user_id: UUID) -> None:
        module_codes = {s.stage_code for s in self._stages() if s.stage_type == rules.STAGE_TYPE_MODULE}
        if len(set(order)) != len(order) or not set(order) <= module_codes:
            raise ValueError("module_order must list Sale Ready module codes, each once")
        get_program_guide_service(self.db).set_custom_order(engagement, order, user_id)

    def reset_module_order(self, engagement: Engagement) -> None:
        get_program_guide_service(self.db).reset_custom_order(engagement)

    # ------------------------------------------------------------------
    # Stage detail and actions
    # ------------------------------------------------------------------
    def _dd_dict(self, item: EngagementDDItem, stage_titles: Dict[str, str]) -> Dict[str, Any]:
        return {
            "id": item.id,
            "item_key": item.item_key,
            "stage_code": item.stage_code,
            "stage_title": stage_titles.get(item.stage_code, item.stage_code),
            "category_code": item.category_code,
            "category": item.category,
            "sub_item_code": item.sub_item_code,
            "sub_item": item.sub_item,
            "document_required": item.document_required,
            "action_step": item.action_step,
            "display_order": item.display_order,
            "status": item.status,
            "gap_handling": item.gap_handling,
            "flag_for_m8": item.flag_for_m8,
            "responsible_user_id": item.responsible_user_id,
            "notes": item.notes,
            "date_completed": item.date_completed,
            "status_changed_at": item.status_changed_at,
        }

    def _task_dict(self, task: Task, templates: Dict[UUID, ProgramTaskTemplate]) -> Dict[str, Any]:
        template = templates.get(task.source_task_template_id) if task.source_task_template_id else None
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "section": task.section,
            "group_title": template.group_title if template else None,
            "status": task.status,
            "sale_ready_state": task.sale_ready_state,
            "assigned_to_user_id": (task.assigned_to_user_ids or [None])[0],
            "due_date": task.due_date,
            "notes": task.task_notes,
            "from_template": template is not None,
        }

    def get_stage_detail(self, engagement: Engagement, stage_code: str, actor: User) -> Dict[str, Any]:
        stage = self._stage_or_404(stage_code)
        self.ensure_initialized(engagement, actor)
        summaries, _ = self._summaries(engagement)
        entry = summaries[stage_code]
        state = entry["state"]
        stage_titles = {code: s["stage"].title for code, s in summaries.items()}

        templates = {t.id: t for t in self._task_templates(stage_code)}
        template_order = {t.id: t.default_order for t in templates.values()}
        tasks = sorted(
            entry["tasks"],
            key=lambda t: (
                SECTION_ORDER.get(t.section, 9),
                template_order.get(t.source_task_template_id, 10_000),
                t.created_at or datetime.min,
            ),
        )
        qa = rules.qa_check(entry["snapshots"], entry["dd_statuses"])

        completed_by = None
        if state and state.completed_by_user_id:
            user = self.db.query(User).filter(User.id == state.completed_by_user_id).first()
            completed_by = _display_name(user) if user else None

        flagged = []
        if stage_code in pinned_last_modules(PROGRAM_SALE_READY):
            flagged = [
                self._dd_dict(d, stage_titles)
                for d in self._dd_items(engagement.id) if d.flag_for_m8
            ]

        return {
            "stage": entry["summary"],
            "task_creation": stage.task_creation,
            "lead_advisor_id": state.lead_advisor_id if state else None,
            "started_at": state.started_at if state else None,
            "completed_at": state.completed_at if state else None,
            "completed_by_name": completed_by,
            "updated_at": state.updated_at if state else None,
            "qa": qa._asdict(),
            "tasks": [self._task_dict(t, templates) for t in tasks],
            "template_preview": [] if entry["summary"]["tasks_created"] else [
                {"title": t.title, "section": t.section, "group_title": t.group_title}
                for t in templates.values()
            ],
            "dd_items": [self._dd_dict(d, stage_titles) for d in entry["dd"]],
            "flagged_for_review": flagged,
            "ui_config": stage.ui_config,
            "people": self.people(engagement),
        }

    def start_stage(self, engagement: Engagement, stage_code: str, user: User) -> None:
        stage = self._stage_or_404(stage_code)
        state = self._state_or_404(engagement, stage_code, user)
        if state.status == rules.STAGE_STATE_NOT_STARTED:
            state.status = rules.STAGE_STATE_STARTED
            state.started_at = _now()
            state.started_by_user_id = user.id
            state.start_date = state.start_date or date.today()
        if stage.task_creation == TASK_CREATION_ON_START:
            # Idempotent: templates that already have a live task are skipped.
            self._create_template_tasks(engagement, stage_code, state, self._creator_id(engagement, user))
        self.db.commit()

    def complete_stage(self, engagement: Engagement, stage_code: str, user: User,
                       original_user: Optional[User] = None) -> None:
        stage = self._stage_or_404(stage_code)
        state = self._state_or_404(engagement, stage_code, user)
        if state.status == rules.STAGE_STATE_COMPLETED:
            return
        if stage.task_creation == TASK_CREATION_ON_START and state.status == rules.STAGE_STATE_NOT_STARTED:
            raise ValueError("Start this module before marking it complete")
        tasks = self._tasks(engagement.id, stage_code)
        dd = self._dd_items(engagement.id, stage_code)
        qa = rules.qa_check(
            [rules.TaskSnapshot(t.section, t.status, t.sale_ready_state) for t in tasks],
            [d.status for d in dd],
        )
        if not qa.passed:
            raise ValueError("Cannot mark complete: " + "; ".join(qa.reasons))
        state.status = rules.STAGE_STATE_COMPLETED
        state.completed_at = _now()
        state.completed_by_user_id = user.id
        state.completed_by_original_user_id = original_user.id if original_user else None
        self.db.commit()

    def reopen_stage(self, engagement: Engagement, stage_code: str, user: User) -> None:
        self._stage_or_404(stage_code)
        state = self._state_or_404(engagement, stage_code, user)
        if state.status != rules.STAGE_STATE_COMPLETED:
            return
        state.status = rules.STAGE_STATE_STARTED
        state.completed_at = None
        state.completed_by_user_id = None
        state.completed_by_original_user_id = None
        self.db.commit()

    def update_stage(self, engagement: Engagement, stage_code: str, fields: Dict[str, Any], user: User) -> None:
        self._stage_or_404(stage_code)
        state = self._state_or_404(engagement, stage_code, user)
        if "lead_advisor_id" in fields:
            self._validate_member(engagement, fields["lead_advisor_id"], advisors_only=True)
        start = fields.get("start_date", state.start_date)
        due = fields.get("due_date", state.due_date)
        if start and due and due < start:
            raise ValueError("Due date cannot be before the start date")
        for name in ("start_date", "due_date", "lead_advisor_id"):
            if name in fields:
                setattr(state, name, fields[name])
        self.db.commit()

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------
    def add_task(self, engagement: Engagement, stage_code: str, title: str, user: User) -> None:
        self._stage_or_404(stage_code)
        self._state_or_404(engagement, stage_code, user)
        self.db.add(Task(
            engagement_id=engagement.id,
            created_by_user_id=user.id,
            title=title.strip(),
            task_type="manual",
            status=rules.TASK_STATUS_PENDING,
            module_reference=stage_code,
            section=rules.SECTION_CLIENT_SPECIFIC,
        ))
        self.db.commit()

    def update_task(self, engagement: Engagement, task_id: UUID, fields: Dict[str, Any]) -> str:
        """Returns the task's stage code so the caller can re-read that stage."""
        stage_codes = {s.stage_code for s in self._stages()}
        task = self.db.query(Task).filter(
            Task.id == task_id,
            Task.engagement_id == engagement.id,
            Task.is_deleted == False,  # noqa: E712
            Task.section.isnot(None),
        ).first()
        if not task or task.module_reference not in stage_codes:
            raise SaleReadyNotFound("Task not found")

        if "status" in fields:
            new_status = fields["status"]
            if new_status not in TASK_STATUSES:
                raise ValueError(f"Invalid task status {new_status!r}")
            if new_status == rules.TASK_STATUS_COMPLETED and task.status != rules.TASK_STATUS_COMPLETED:
                task.completed_at = _now()
            elif new_status != rules.TASK_STATUS_COMPLETED:
                task.completed_at = None
            task.status = new_status
            # Done and "not required" are alternatives, not both at once.
            if new_status == rules.TASK_STATUS_COMPLETED:
                task.sale_ready_state = None
        if "sale_ready_state" in fields:
            state = rules.validate_task_state(fields["sale_ready_state"] or None)
            task.sale_ready_state = state
            # Marking a completed task N/A or blocked takes it off done, so the
            # two never contradict each other.
            if state is not None and task.status == rules.TASK_STATUS_COMPLETED:
                task.status = rules.TASK_STATUS_PENDING
                task.completed_at = None
        if "assigned_to_user_id" in fields:
            assignee = fields["assigned_to_user_id"]
            self._validate_member(engagement, assignee)
            task.assigned_to_user_ids = [assignee] if assignee else None
        if "due_date" in fields:
            task.due_date = fields["due_date"]
        if "notes" in fields:
            task.task_notes = fields["notes"] or None
        self.db.commit()
        return task.module_reference

    # ------------------------------------------------------------------
    # DD checklist
    # ------------------------------------------------------------------
    def get_dd_checklist(self, engagement: Engagement, actor: Optional[User] = None) -> Dict[str, Any]:
        self.ensure_initialized(engagement, actor)
        stages = self._stages()
        titles = {s.stage_code: s.title for s in stages}
        items = self._dd_items(engagement.id)
        # Master list reads category by category, as in the client's checklist.
        items.sort(key=lambda d: (d.display_order, d.item_key))

        def count(status: Optional[str]) -> int:
            return sum(1 for d in items if d.status == status)

        used = {d.stage_code for d in items}
        return {
            "items": [self._dd_dict(d, titles) for d in items],
            "stats": {
                "total": len(items),
                "yes": count(rules.DD_STATUS_YES),
                "in_progress": count(rules.DD_STATUS_IN_PROGRESS),
                "no": count(rules.DD_STATUS_NO),
                "not_applicable": count(rules.DD_STATUS_NOT_APPLICABLE),
                "no_status": count(None),
                "flagged": sum(1 for d in items if d.flag_for_m8),
                "referred": sum(
                    1 for d in items
                    if rules.effective_gap_handling(d.status, d.gap_handling) == rules.GAP_REFER
                ),
            },
            "stages": [{"stage_code": s.stage_code, "title": s.title} for s in stages if s.stage_code in used],
            "people": self.people(engagement),
        }

    def update_dd_item(self, engagement: Engagement, item_id: UUID, fields: Dict[str, Any], user: User) -> Dict[str, Any]:
        item = self.db.query(EngagementDDItem).filter(
            EngagementDDItem.id == item_id, EngagementDDItem.engagement_id == engagement.id,
        ).first()
        if not item:
            raise SaleReadyNotFound("DD item not found")

        new_status = item.status
        if "status" in fields:
            new_status = rules.validate_dd_status(fields["status"] or None)
        if "gap_handling" in fields:
            item.gap_handling = rules.validate_gap_handling(new_status, fields["gap_handling"] or None)
        if new_status != item.status:
            item.status = new_status
            item.status_changed_at = _now()
            item.status_changed_by_user_id = user.id
            item.date_completed = date.today() if new_status == rules.DD_STATUS_YES else None
        if "responsible_user_id" in fields:
            self._validate_member(engagement, fields["responsible_user_id"])
            item.responsible_user_id = fields["responsible_user_id"]
        if "notes" in fields:
            item.notes = fields["notes"] or None
        if "flag_for_m8" in fields and fields["flag_for_m8"] is not None:
            item.flag_for_m8 = bool(fields["flag_for_m8"])
        self.db.commit()
        self.db.refresh(item)
        return self._dd_dict(item, {s.stage_code: s.title for s in self._stages()})


def get_sale_ready_service(db: Session) -> SaleReadyService:
    return SaleReadyService(db)
