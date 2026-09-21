"""
Sale Ready Sale Planner and Close-out: the two stages with their own screen.

The Sale Planner stores answers by the stable keys in the SALE_PLANNER stage's
ui_config (files/sale_ready/sale_planner.json). Closing the program records who
closed it and ends the engagement with the existing lifecycle status, in one
transaction.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.engagement import Engagement
from app.models.sale_ready import EngagementProgramCloseout, EngagementSalePlanner, ProgramStage
from app.models.user import User
from app.services.engagement_status import STATUS_ACTIVE, STATUS_ENDED
from app.services.program_registry import PROGRAM_SALE_READY

logger = logging.getLogger(__name__)

SALE_PLANNER_STAGE = "SALE_PLANNER"
DICT_FIELDS = ("value_propositions", "marketing_answers", "issues")


class CloseoutPermissionError(PermissionError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _name(user: Optional[User]) -> Optional[str]:
    if not user:
        return None
    full = " ".join(p for p in (user.first_name, user.last_name) if p)
    return user.name or full or user.email


class SaleReadyPlannerService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Sale Planner
    # ------------------------------------------------------------------
    def _config(self) -> Dict[str, Any]:
        stage = self.db.query(ProgramStage).filter(
            ProgramStage.program_type == PROGRAM_SALE_READY,
            ProgramStage.stage_code == SALE_PLANNER_STAGE,
            ProgramStage.is_active == True,  # noqa: E712
        ).first()
        if not stage or not stage.ui_config:
            raise ValueError("The Sale Planner is not configured. Run scripts/seed_sale_ready_program.py")
        return stage.ui_config

    def _planner(self, engagement_id) -> Optional[EngagementSalePlanner]:
        return self.db.query(EngagementSalePlanner).filter(EngagementSalePlanner.engagement_id == engagement_id).first()

    def get_sale_planner(self, engagement: Engagement) -> Dict[str, Any]:
        """A read never creates the row; an engagement with none gets the empty answers."""
        config = self._config()
        row = self._planner(engagement.id)
        updated_by = None
        if row and row.updated_by_user_id:
            updated_by = self.db.query(User).filter(User.id == row.updated_by_user_id).first()
        issues = row.issues if row else {}
        return {
            "config": config,
            "sale_type": row.sale_type if row else None,
            "sale_structures": row.sale_structures if row else [],
            "value_propositions": row.value_propositions if row else {},
            "marketing_answers": row.marketing_answers if row else {},
            "issues": issues,
            "issues_addressed": sum(1 for v in issues.values() if v.get("addressed")),
            "issues_total": len(config.get("issues", [])),
            "updated_at": row.updated_at if row else None,
            "updated_by_name": _name(updated_by),
        }

    @staticmethod
    def _keys(config: Dict[str, Any], name: str) -> set:
        return {item["key"] for item in config.get(name, [])}

    def _validate(self, config: Dict[str, Any], fields: Dict[str, Any]) -> None:
        if "sale_type" in fields and fields["sale_type"] is not None:
            if fields["sale_type"] not in self._keys(config, "sale_types"):
                raise ValueError(f"Unknown sale type {fields['sale_type']!r}")
        if "sale_structures" in fields:
            structures = fields["sale_structures"] or []
            if len(set(structures)) != len(structures) or not set(structures) <= self._keys(config, "sale_structures"):
                raise ValueError("sale_structures must list known structure keys, each once")
        text_maps = {
            "value_propositions": "value_proposition_structures",
            "marketing_answers": "marketing_questions",
        }
        for field, source in text_maps.items():
            unknown = set(fields.get(field) or {}) - self._keys(config, source)
            if unknown:
                raise ValueError(f"Unknown {field} keys: {', '.join(sorted(unknown))}")
            for value in (fields.get(field) or {}).values():
                if value is not None and not isinstance(value, str):
                    raise ValueError(f"{field} values must be text")
        issues = fields.get("issues") or {}
        unknown = set(issues) - self._keys(config, "issues")
        if unknown:
            raise ValueError(f"Unknown issue keys: {', '.join(sorted(unknown))}")
        for value in issues.values():
            if value is None:
                continue
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("addressed", False), bool)
                or not isinstance(value.get("note") or "", str)
            ):
                raise ValueError('Each issue must be {"addressed": bool, "note": text}')

    def update_sale_planner(self, engagement: Engagement, fields: Dict[str, Any], user: User) -> Dict[str, Any]:
        """
        sale_type and sale_structures are replaced. The three answer maps are
        merged by key; a null value removes that key's answer.
        """
        config = self._config()
        self._validate(config, fields)

        row = self._planner(engagement.id)
        if row is None:
            row = EngagementSalePlanner(engagement_id=engagement.id)
            self.db.add(row)
        if "sale_type" in fields:
            row.sale_type = fields["sale_type"]
        if "sale_structures" in fields:
            row.sale_structures = list(fields["sale_structures"] or [])
        for field in DICT_FIELDS:
            if field not in fields or fields[field] is None:
                continue
            # A new dict, not an in-place change, so the JSONB column is flushed.
            merged = dict(getattr(row, field) or {})
            for key, value in fields[field].items():
                if value is None:
                    merged.pop(key, None)
                elif field == "issues":
                    merged[key] = {"addressed": bool(value.get("addressed", False)), "note": value.get("note") or ""}
                else:
                    merged[key] = value
            setattr(row, field, merged)
        row.updated_by_user_id = user.id
        self.db.commit()
        return self.get_sale_planner(engagement)

    # ------------------------------------------------------------------
    # Close-out
    # ------------------------------------------------------------------
    def _closeout(self, engagement_id) -> Optional[EngagementProgramCloseout]:
        return self.db.query(EngagementProgramCloseout).filter(
            EngagementProgramCloseout.engagement_id == engagement_id
        ).first()

    def get_closeout(self, engagement: Engagement) -> Dict[str, Any]:
        row = self._closeout(engagement.id)
        closed_by = None
        if row and row.closed_by_user_id:
            closed_by = self.db.query(User).filter(User.id == row.closed_by_user_id).first()
        return {
            "fresh_appraisal_required": row.fresh_appraisal_required if row else False,
            "referred_to_benchmark": row.referred_to_benchmark if row else False,
            "ongoing_assistance": row.ongoing_assistance if row else None,
            "is_closed": bool(row and row.closed_at),
            "closed_at": row.closed_at if row else None,
            "closed_by_name": _name(closed_by),
            "engagement_status": engagement.status,
            "engagement_completed_at": engagement.completed_at,
        }

    def _apply_decisions(self, row: EngagementProgramCloseout, fields: Dict[str, Any]) -> None:
        for name in ("fresh_appraisal_required", "referred_to_benchmark"):
            if name in fields and fields[name] is not None:
                setattr(row, name, bool(fields[name]))
        if "ongoing_assistance" in fields:
            row.ongoing_assistance = (fields["ongoing_assistance"] or "").strip() or None

    def _get_or_new_closeout(self, engagement: Engagement) -> EngagementProgramCloseout:
        row = self._closeout(engagement.id)
        if row is None:
            row = EngagementProgramCloseout(engagement_id=engagement.id)
            self.db.add(row)
        return row

    def update_closeout(self, engagement: Engagement, fields: Dict[str, Any]) -> Dict[str, Any]:
        row = self._closeout(engagement.id)
        if row and row.closed_at:
            raise ValueError("The program is closed. Reopen it to change the close-out decisions")
        row = self._get_or_new_closeout(engagement)
        self._apply_decisions(row, fields)
        self.db.commit()
        return self.get_closeout(engagement)

    def close_program(
        self,
        engagement: Engagement,
        fields: Dict[str, Any],
        confirm_without_referral: bool,
        user: User,
        original_user: Optional[User],
        can_change_status: bool,
    ) -> Dict[str, Any]:
        """
        Validate first, then save the decisions, close the program and end the
        engagement in a single commit. Any failure rolls back all of it.
        """
        if not can_change_status:
            raise CloseoutPermissionError("You do not have permission to end this engagement")
        existing = self._closeout(engagement.id)
        if existing and existing.closed_at:
            raise ValueError("The program is already closed")
        referred = fields.get("referred_to_benchmark")
        if referred is None:
            referred = existing.referred_to_benchmark if existing else False
        if not referred and not confirm_without_referral:
            raise ValueError("Confirm closing the program without referring the client to Benchmark Business Sales")

        try:
            row = self._get_or_new_closeout(engagement)
            self._apply_decisions(row, fields)
            now = _now()
            row.closed_at = now
            row.closed_by_user_id = user.id
            row.closed_by_original_user_id = original_user.id if original_user else None
            # The existing lifecycle "end": hides tasks, and automation never overwrites it.
            engagement.status = STATUS_ENDED
            engagement.completed_at = now
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        logger.info("Sale Ready program closed for engagement %s by user %s", engagement.id, user.id)
        return self.get_closeout(engagement)

    def reopen_program(self, engagement: Engagement, user: User, can_change_status: bool) -> Dict[str, Any]:
        """Clears the close and recommences the engagement, as the lifecycle Recommence does."""
        if not can_change_status:
            raise CloseoutPermissionError("You do not have permission to recommence this engagement")
        row = self._closeout(engagement.id)
        if not row or not row.closed_at:
            raise ValueError("The program is not closed")
        try:
            row.closed_at = None
            row.closed_by_user_id = None
            row.closed_by_original_user_id = None
            # Only undo our own "ended"; a status set since then through the lifecycle stays.
            if engagement.status == STATUS_ENDED:
                engagement.status = STATUS_ACTIVE
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        logger.info("Sale Ready program reopened for engagement %s by user %s", engagement.id, user.id)
        return self.get_closeout(engagement)


def get_sale_ready_planner_service(db: Session) -> SaleReadyPlannerService:
    return SaleReadyPlannerService(db)
