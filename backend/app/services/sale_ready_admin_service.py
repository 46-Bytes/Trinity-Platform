"""
Sale Ready Management: the master content admins edit for future engagements.

Three things are editable - the program guide, the task templates and the due
diligence checklist. Everything here writes master rows only. Nothing in this
module touches `tasks` or `engagement_dd_item`, which is what keeps a live
engagement unchanged when an admin edits the master content: an engagement's
tasks and DD items are copies taken when it was created, and its guide is a
frozen snapshot (see SaleReadyService).

Fixed by the brief and enforced here rather than by convention:

  - the 15 stages cannot be created, deleted or reordered;
  - the 16 DD categories and their sub-items cannot be created or restructured,
    so a new checklist item is filed under a pair that already exists;
  - stage_code, template_key and item_key are immutable, because they are the
    keys existing engagements were copied against;
  - removing a template retires it (is_active = False). Nothing is ever deleted;
    engagement_dd_item.template_item_id is ON DELETE RESTRICT, so a hard delete
    of a materialised item would fail anyway.
"""
import logging
import re
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.sale_ready import (
    ProgramDDTemplate,
    ProgramGuideContent,
    ProgramStage,
    ProgramTaskTemplate,
)
from app.services import sale_ready_rules as rules
from app.services.program_registry import PROGRAM_SALE_READY
from app.services.sale_ready_service import active_stages, find_stage, normalise_stage_guide

logger = logging.getLogger(__name__)

GUIDE_FIELDS = ("purpose", "steps", "watch", "templates", "run_with")
TASK_PRIORITIES = frozenset({"low", "medium", "high"})
SECTION_ABBREV = {rules.SECTION_MUST_DO: "MUST", rules.SECTION_OPTIONAL: "OPT"}


class SaleReadyAdminNotFound(LookupError):
    pass


class SaleReadyAdminService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Stages (read-only structure)
    # ------------------------------------------------------------------
    def _stages(self) -> List[ProgramStage]:
        return active_stages(self.db)

    def _stage_or_404(self, stage_code: str) -> ProgramStage:
        stage = find_stage(self.db, stage_code)
        if not stage:
            raise SaleReadyAdminNotFound(f"Stage {stage_code} not found")
        return stage

    # ------------------------------------------------------------------
    # Program guide
    # ------------------------------------------------------------------
    def _program_guide_row(self) -> Optional[ProgramGuideContent]:
        return self.db.query(ProgramGuideContent).filter(
            ProgramGuideContent.program_type == PROGRAM_SALE_READY,
        ).first()

    @staticmethod
    def _stage_guide(stage: ProgramStage) -> Dict[str, Any]:
        return normalise_stage_guide(stage.guide)

    def get_guide(self) -> Dict[str, Any]:
        row = self._program_guide_row()
        content = dict(row.content or {}) if row else {}
        return {
            "program": {
                "workflow": content.get("workflow") or [],
                "rules": content.get("rules") or [],
            },
            "stages": [
                {
                    "stage_code": s.stage_code,
                    "display_code": s.display_code,
                    "stage_type": s.stage_type,
                    "title": s.title,
                    "description": s.description,
                    "default_order": s.default_order,
                    "task_creation": s.task_creation,
                    "ui_variant": s.ui_variant,
                    "guide": self._stage_guide(s),
                }
                for s in self._stages()
            ],
        }

    def update_program_guide(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Replace the workflow steps, the rules, or both. Absent fields are left alone."""
        known = {s.stage_code for s in self._stages()} | {"modules"}
        for step in fields.get("workflow") or []:
            if step["stage"] not in known:
                raise ValueError(f"Unknown workflow stage {step['stage']!r}")

        row = self._program_guide_row()
        if row is None:
            row = ProgramGuideContent(
                program_type=PROGRAM_SALE_READY, content={"workflow": [], "rules": []},
            )
            self.db.add(row)
        # A new dict, not an in-place change, so the JSONB column is flushed.
        content = dict(row.content or {})
        for name in ("workflow", "rules"):
            if fields.get(name) is not None:
                content[name] = fields[name]
        content.setdefault("workflow", [])
        content.setdefault("rules", [])
        row.content = content
        self.db.commit()
        return self.get_guide()

    def update_stage_guide(self, stage_code: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Patch one stage's guide. The stage itself is never created or removed here."""
        stage = self._stage_or_404(stage_code)
        guide = self._stage_guide(stage)
        for name in GUIDE_FIELDS:
            if name in fields and fields[name] is not None:
                guide[name] = fields[name]
        if "run_with" in fields:
            value = (fields["run_with"] or "").strip() if fields["run_with"] is not None else None
            guide["run_with"] = value or None
        stage.guide = guide
        self.db.commit()
        return self.get_guide()

    # ------------------------------------------------------------------
    # Task templates
    # ------------------------------------------------------------------
    def _task_template_or_404(self, template_id: UUID) -> ProgramTaskTemplate:
        row = self.db.query(ProgramTaskTemplate).filter(
            ProgramTaskTemplate.id == template_id,
            ProgramTaskTemplate.program_type == PROGRAM_SALE_READY,
        ).first()
        if not row:
            raise SaleReadyAdminNotFound("Task template not found")
        return row

    def list_task_templates(self, include_retired: bool = True) -> List[ProgramTaskTemplate]:
        query = self.db.query(ProgramTaskTemplate).filter(
            ProgramTaskTemplate.program_type == PROGRAM_SALE_READY,
        )
        if not include_retired:
            query = query.filter(ProgramTaskTemplate.is_active == True)  # noqa: E712
        return query.order_by(
            ProgramTaskTemplate.stage_code.asc(),
            ProgramTaskTemplate.section.asc(),
            ProgramTaskTemplate.default_order.asc(),
        ).all()

    def _next_template_key(self, stage_code: str, section: str) -> str:
        """
        Server-generated so two admins cannot collide on a key, and so a key
        never has to be typed. Retired rows still count - their keys are taken.
        """
        prefix = f"{stage_code}-{SECTION_ABBREV[section]}-"
        taken = {
            row[0] for row in self.db.query(ProgramTaskTemplate.template_key).filter(
                ProgramTaskTemplate.program_type == PROGRAM_SALE_READY,
                ProgramTaskTemplate.stage_code == stage_code,
            )
        }
        highest = 0
        for key in taken:
            match = re.fullmatch(re.escape(prefix) + r"(\d+)", key or "")
            if match:
                highest = max(highest, int(match.group(1)))
        return f"{prefix}{highest + 1:02d}"

    def create_task_template(self, fields: Dict[str, Any]) -> ProgramTaskTemplate:
        stage = self._stage_or_404(fields["stage_code"])
        priority = fields.get("priority") or "medium"
        if priority not in TASK_PRIORITIES:
            raise ValueError(f"priority must be one of {', '.join(sorted(TASK_PRIORITIES))}")

        section = fields["section"]
        last = max(
            (t.default_order for t in self.list_task_templates()
             if t.stage_code == stage.stage_code and t.section == section),
            default=0,
        )
        row = ProgramTaskTemplate(
            program_type=PROGRAM_SALE_READY,
            stage_code=stage.stage_code,
            template_key=self._next_template_key(stage.stage_code, section),
            section=section,
            group_title=(fields.get("group_title") or None),
            title=fields["title"].strip(),
            description=(fields.get("description") or None),
            priority=priority,
            default_order=last + 1,
            due_offset_days=fields.get("due_offset_days"),
            is_active=True,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        logger.info("Sale Ready task template %s created for %s", row.template_key, row.stage_code)
        return row

    def update_task_template(self, template_id: UUID, fields: Dict[str, Any]) -> ProgramTaskTemplate:
        row = self._task_template_or_404(template_id)
        if "priority" in fields and fields["priority"] is not None:
            if fields["priority"] not in TASK_PRIORITIES:
                raise ValueError(f"priority must be one of {', '.join(sorted(TASK_PRIORITIES))}")
        for name in ("section", "title", "description", "group_title", "priority",
                     "due_offset_days", "is_active"):
            if name in fields and fields[name] is not None:
                setattr(row, name, fields[name])
        self.db.commit()
        self.db.refresh(row)
        return row

    def retire_task_template(self, template_id: UUID) -> None:
        """Removing a template retires it. Tasks already created from it are untouched."""
        row = self._task_template_or_404(template_id)
        row.is_active = False
        self.db.commit()
        logger.info("Sale Ready task template %s retired", row.template_key)

    def reorder_task_templates(self, ids: Sequence[UUID]) -> List[ProgramTaskTemplate]:
        """
        Reorder within one stage and section. Every id must be in that group, and
        the whole group must be listed, so no row is left with a stale position.
        """
        rows = [self._task_template_or_404(i) for i in ids]
        groups = {(r.stage_code, r.section) for r in rows}
        if len(groups) != 1:
            raise ValueError("Reorder one stage and section at a time")
        stage_code, section = groups.pop()
        siblings = [
            t for t in self.list_task_templates(include_retired=False)
            if t.stage_code == stage_code and t.section == section
        ]
        if {t.id for t in siblings} != set(ids):
            raise ValueError("Reorder must list every active template in the stage and section, once")
        for position, row in enumerate(rows, start=1):
            row.default_order = position
        self.db.commit()
        return rows

    # ------------------------------------------------------------------
    # Due diligence checklist
    # ------------------------------------------------------------------
    def _dd_template_or_404(self, template_id: UUID) -> ProgramDDTemplate:
        row = self.db.query(ProgramDDTemplate).filter(
            ProgramDDTemplate.id == template_id,
            ProgramDDTemplate.program_type == PROGRAM_SALE_READY,
        ).first()
        if not row:
            raise SaleReadyAdminNotFound("DD checklist item not found")
        return row

    def list_dd_templates(self, include_retired: bool = True) -> List[ProgramDDTemplate]:
        query = self.db.query(ProgramDDTemplate).filter(
            ProgramDDTemplate.program_type == PROGRAM_SALE_READY,
        )
        if not include_retired:
            query = query.filter(ProgramDDTemplate.is_active == True)  # noqa: E712
        return query.order_by(ProgramDDTemplate.default_order.asc()).all()

    def dd_categories(self) -> List[Dict[str, Any]]:
        """
        The existing category / sub-item structure, which admins choose from but
        cannot change. Retired rows still define the structure, so a category is
        not lost when its last item is retired.
        """
        categories: Dict[str, Dict[str, Any]] = {}
        for row in self.list_dd_templates():
            cat = categories.setdefault(
                row.category_code,
                {"category_code": row.category_code, "category": row.category, "sub_items": {}},
            )
            cat["sub_items"].setdefault(row.sub_item_code, {
                "sub_item_code": row.sub_item_code,
                "sub_item": row.sub_item or "",
                "stage_code": row.stage_code,
            })
        return [
            {**cat, "sub_items": sorted(cat["sub_items"].values(), key=_sub_item_sort)}
            for cat in sorted(categories.values(), key=lambda c: _code_sort(c["category_code"]))
        ]

    def _next_item_key(self) -> str:
        taken = {
            row[0] for row in self.db.query(ProgramDDTemplate.item_key).filter(
                ProgramDDTemplate.program_type == PROGRAM_SALE_READY,
            )
        }
        highest = 0
        for key in taken:
            match = re.fullmatch(r"DD-(\d+)", key or "")
            if match:
                highest = max(highest, int(match.group(1)))
        return f"DD-{highest + 1:03d}"

    def create_dd_template(self, fields: Dict[str, Any]) -> ProgramDDTemplate:
        """
        File a new item under an existing category and sub-item. The stage and the
        category name come from that pair, so neither the structure nor the
        stage mapping can be changed from here.
        """
        category_code, sub_item_code = fields["category_code"], fields["sub_item_code"]
        sibling = next(
            (r for r in self.list_dd_templates()
             if r.category_code == category_code and r.sub_item_code == sub_item_code),
            None,
        )
        if sibling is None:
            raise ValueError(
                f"Unknown category / sub-item {category_code}/{sub_item_code}. "
                "New checklist items are filed under an existing sub-item."
            )
        last = max((r.default_order for r in self.list_dd_templates()), default=0)
        row = ProgramDDTemplate(
            program_type=PROGRAM_SALE_READY,
            item_key=self._next_item_key(),
            stage_code=sibling.stage_code,
            category_code=sibling.category_code,
            category=sibling.category,
            sub_item_code=sibling.sub_item_code,
            sub_item=sibling.sub_item,
            document_required=fields["document_required"].strip(),
            action_step=(fields.get("action_step") or None),
            default_order=last + 1,
            is_active=True,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        logger.info("Sale Ready DD item %s created under %s", row.item_key, row.sub_item_code)
        return row

    def update_dd_template(self, template_id: UUID, fields: Dict[str, Any]) -> ProgramDDTemplate:
        row = self._dd_template_or_404(template_id)
        for name in ("document_required", "action_step", "sub_item", "is_active"):
            if name in fields and fields[name] is not None:
                setattr(row, name, fields[name])
        self.db.commit()
        self.db.refresh(row)
        return row

    def retire_dd_template(self, template_id: UUID) -> None:
        """Removing an item retires it. Engagements that already carry it keep it."""
        row = self._dd_template_or_404(template_id)
        row.is_active = False
        self.db.commit()
        logger.info("Sale Ready DD item %s retired", row.item_key)

    def reorder_dd_templates(self, ids: Sequence[UUID]) -> List[ProgramDDTemplate]:
        """Reorder within one sub-item; the whole sub-item must be listed."""
        rows = [self._dd_template_or_404(i) for i in ids]
        groups = {(r.category_code, r.sub_item_code) for r in rows}
        if len(groups) != 1:
            raise ValueError("Reorder one sub-item at a time")
        category_code, sub_item_code = groups.pop()
        siblings = [
            r for r in self.list_dd_templates(include_retired=False)
            if r.category_code == category_code and r.sub_item_code == sub_item_code
        ]
        if {r.id for r in siblings} != set(ids):
            raise ValueError("Reorder must list every active item in the sub-item, once")
        base = min(r.default_order for r in siblings)
        for offset, row in enumerate(rows):
            row.default_order = base + offset
        self.db.commit()
        return rows


def _code_sort(code: str):
    """'10' after '9': sort numerically where the code is a number."""
    return (0, int(code)) if code.isdigit() else (1, code)


def _sub_item_sort(item: Dict[str, str]):
    parts = str(item.get("sub_item_code") or "").split(".")
    return tuple(int(p) if p.isdigit() else 0 for p in parts) or (0,)


def get_sale_ready_admin_service(db: Session) -> SaleReadyAdminService:
    return SaleReadyAdminService(db)
