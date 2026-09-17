"""
Program Guide service: composes module card content with the recommended
module order for an engagement, and tracks advisor overrides.

The recommended order is computed live from the latest completed diagnostic for
the engagement - never cached - since the computation is cheap (sorting eleven
in-memory scores, no LLM calls).

The diagnostic is the single source. The order used to come from the BBA
("Recommendations Report Builder") draft findings, matching each finding's
freeform `priority_area` back to a module code - a match documented as fragile
across module renames, and one that silently degraded to the default taxonomy
whenever it failed. Diagnostic module scores are already keyed by module code,
so nothing has to be matched at all: the worst-scoring module is worked first.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.diagnostic import Diagnostic
from app.models.engagement import Engagement
from app.models.program_guide import EngagementProgramModuleState, ProgramModuleContent
from app.services.scoring_service import ScoringService


class ProgramGuideService:
    """Service for composing and ordering Program Guide module cards."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------
    def get_content(self, program_type: str) -> List[ProgramModuleContent]:
        return (
            self.db.query(ProgramModuleContent)
            .filter(
                ProgramModuleContent.program_type == program_type,
                ProgramModuleContent.is_active == True,  # noqa: E712
            )
            .order_by(ProgramModuleContent.display_order.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------
    @staticmethod
    def _scores_by_module(diagnostic: Optional[Diagnostic], canonical: Dict[str, str]) -> Dict[str, float]:
        """
        The numeric module scores from a diagnostic, keyed by module code.

        Only codes in the canonical taxonomy are kept, and only where the score
        is genuinely numeric. A module the diagnostic did not score is absent
        from the mapping rather than present as None, so callers cannot
        accidentally sort a missing score as if it were zero - which would rank
        an unmeasured module as the single worst thing in the business.
        """
        if diagnostic is None:
            return {}
        blob = (diagnostic.module_scores or {}).get("modules")
        if not isinstance(blob, dict):
            return {}

        scores: Dict[str, float] = {}
        for code in canonical:
            entry = blob.get(code)
            if not isinstance(entry, dict):
                continue
            score = entry.get("score")
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                continue
            scores[code] = float(score)
        return scores

    def compute_recommended_order(self, engagement: Engagement) -> Dict[str, Any]:
        """
        Compute the recommended V1-V11 order for an engagement, worst-scoring
        module first.

        The diagnostic measures each module on the same 0-5 scale, so the
        weakest area is the one to work on first. Ties fall back to taxonomy
        order, which matters more than it looks: diagnostic scores are averages
        over a handful of answers and ties are common, and without a tiebreak
        two equally-scored modules could swap places between requests and make
        the guide look like it reordered itself.

        Always returns all 11 module codes. Modules the diagnostic did not score
        (roughly a third of the question set is conditional, so a service
        business never answers the warehousing questions) are appended in
        default taxonomy order, so the guide is always fully viewable - there is
        no gating on having a diagnostic at all.
        """
        if engagement.tool != "value_builder":
            return {"source": "unsupported", "order": [], "diagnostic_id": None}

        canonical = ScoringService.VALUE_BUILDER_MODULES
        all_codes = list(canonical.keys())

        diagnostic = self._get_latest_completed_diagnostic(engagement.id)
        scores = self._scores_by_module(diagnostic, canonical)
        if not scores:
            # A diagnostic that exists but scored nothing is reported the same
            # way as no diagnostic at all: the order it produced is the default
            # one, and saying otherwise would credit it with a sequence it did
            # not decide.
            return {"source": "default", "order": all_codes, "diagnostic_id": None}

        taxonomy_position = {code: i for i, code in enumerate(all_codes)}
        scored = sorted(
            (c for c in all_codes if c in scores),
            key=lambda c: (scores[c], taxonomy_position[c]),
        )
        unscored = [c for c in all_codes if c not in scores]

        return {
            "source": "diagnostic",
            "order": scored + unscored,
            "diagnostic_id": str(diagnostic.id),
        }

    def _get_state(self, engagement_id: UUID) -> Optional[EngagementProgramModuleState]:
        return (
            self.db.query(EngagementProgramModuleState)
            .filter(EngagementProgramModuleState.engagement_id == engagement_id)
            .first()
        )

    def get_effective_order(self, engagement: Engagement) -> Dict[str, Any]:
        """Merge the computed recommended order with any advisor override."""
        computed = self.compute_recommended_order(engagement)
        state = self._get_state(engagement.id)
        if state and state.custom_order:
            merged = list(state.custom_order) + [c for c in computed["order"] if c not in state.custom_order]
            return {
                **computed,
                "source": "custom",
                "order": merged,
                "custom_order_set_at": state.custom_order_set_at,
                "custom_order_set_by_user_id": str(state.custom_order_set_by_user_id) if state.custom_order_set_by_user_id else None,
            }
        return {**computed, "custom_order_set_at": None, "custom_order_set_by_user_id": None}

    def set_custom_order(self, engagement: Engagement, module_order: List[str], user_id: UUID) -> Dict[str, Any]:
        state = self._get_state(engagement.id)
        now = datetime.now(timezone.utc)
        if state:
            state.custom_order = module_order
            state.custom_order_set_by_user_id = user_id
            state.custom_order_set_at = now
        else:
            state = EngagementProgramModuleState(
                engagement_id=engagement.id,
                program_type=engagement.tool,
                custom_order=module_order,
                custom_order_set_by_user_id=user_id,
                custom_order_set_at=now,
            )
            self.db.add(state)
        self.db.commit()
        return self.get_effective_order(engagement)

    def reset_custom_order(self, engagement: Engagement) -> Dict[str, Any]:
        state = self._get_state(engagement.id)
        if state:
            state.custom_order = None
            state.custom_order_set_by_user_id = None
            state.custom_order_set_at = None
            self.db.commit()
        return self.get_effective_order(engagement)

    # ------------------------------------------------------------------
    # Composed view
    # ------------------------------------------------------------------
    def get_program_guide_view(self, engagement: Engagement) -> Dict[str, Any]:
        content_rows = self.get_content(engagement.tool)
        effective = self.get_effective_order(engagement)
        rank_by_code = {code: i + 1 for i, code in enumerate(effective["order"])}

        modules = []
        for row in content_rows:
            modules.append({
                **row.to_dict(),
                "effective_rank": rank_by_code.get(row.module_code),
            })
        # Order the modules array itself by effective rank. A row the order does
        # not mention - a card published for a code outside the taxonomy - falls
        # back to its authored display_order rather than disappearing.
        modules.sort(
            key=lambda m: m["effective_rank"] if m["effective_rank"] is not None else m["display_order"]
        )

        return {
            "program_type": engagement.tool,
            "order_source": effective["source"],
            "source_diagnostic_id": effective.get("diagnostic_id"),
            "custom_order_set_at": effective.get("custom_order_set_at"),
            "custom_order_set_by_user_id": effective.get("custom_order_set_by_user_id"),
            "modules": modules,
        }

    def get_dashboard_view(self, engagement: Engagement) -> Dict[str, Any]:
        """
        Progress and the module list - the only Program Guide read an owner gets.

        Built by narrowing get_program_guide_view rather than by a second query,
        so the ordering cannot drift between the two. The narrowing is an
        explicit field list: anything not named here does not reach the caller,
        which is the point.

        Status comes from the deliverables engine. Modules with no deliverables
        are absent from that mapping and read as not_started, which is what
        derive_module_status returns for an empty list anyway.
        """
        # Imported here rather than at module scope: program_deliverable_service
        # is the newer subsystem and this keeps the dependency one-directional.
        from app.services.program_deliverable_service import (
            MODULE_STATUS_COMPLETED,
            MODULE_STATUS_IN_PROGRESS,
            MODULE_STATUS_NOT_STARTED,
            get_program_deliverable_service,
        )

        full = self.get_program_guide_view(engagement)
        statuses = get_program_deliverable_service(self.db).get_module_statuses(engagement)

        modules = [
            {
                "module_code": m["module_code"],
                "title": m["title"],
                "effective_rank": m["effective_rank"],
                "status": statuses.get(m["module_code"], MODULE_STATUS_NOT_STARTED),
            }
            for m in full["modules"]
        ]

        def count(status: str) -> int:
            return sum(1 for m in modules if m["status"] == status)

        return {
            "program_type": engagement.tool,
            "modules": modules,
            "total_modules": len(modules),
            "completed_modules": count(MODULE_STATUS_COMPLETED),
            "in_progress_modules": count(MODULE_STATUS_IN_PROGRESS),
            "not_started_modules": count(MODULE_STATUS_NOT_STARTED),
        }

    # ------------------------------------------------------------------
    # Diagnostic insights
    # ------------------------------------------------------------------
    def _get_latest_completed_diagnostic(self, engagement_id: UUID) -> Optional[Diagnostic]:
        return (
            self.db.query(Diagnostic)
            .filter(
                Diagnostic.engagement_id == engagement_id,
                Diagnostic.status == "completed",
                Diagnostic.is_deleted == False,  # noqa: E712
            )
            .order_by(Diagnostic.completed_at.desc())
            .first()
        )

    def compute_module_insights(self, engagement: Engagement) -> Dict[str, Any]:
        """
        Per-module diagnostic state: score, RAG, severity and evidence depth.

        This is the read that compute_value_movement cannot serve. That one is a
        comparison and returns nothing at all below two completed diagnostics,
        which is the ordinary case - most engagements have exactly one. The
        scores are sitting in Diagnostic.module_scores either way; this exposes
        the current position without requiring a prior one to subtract from.

        It reads the same diagnostic that decides the order, so what an advisor
        sees on a module card is exactly what ranked it - the score IS the
        reason for the position, with nothing in between to mismatch.
        """
        canonical = ScoringService.VALUE_BUILDER_MODULES
        if engagement.tool != "value_builder":
            return {
                "program_type": engagement.tool,
                "has_scores": False,
                "modules": [],
            }

        diagnostic = self._get_latest_completed_diagnostic(engagement.id)
        raw_modules: Dict[str, Any] = {}
        if diagnostic:
            modules_blob = (diagnostic.module_scores or {}).get("modules")
            if isinstance(modules_blob, dict):
                raw_modules = modules_blob

        rank_by_code = {
            code: i + 1 for i, code in enumerate(self.get_effective_order(engagement)["order"])
        }

        modules = []
        for code, name in canonical.items():
            entry = raw_modules.get(code) or {}
            score = entry.get("score")
            score = float(score) if isinstance(score, (int, float)) else None
            count = entry.get("count")
            modules.append({
                "module_code": code,
                "module_name": name,
                "score": score,
                "rag": ScoringService.determine_rag_status(score) if score is not None else None,
                "severity": ScoringService.determine_severity(score) if score is not None else None,
                "answered_questions": int(count) if isinstance(count, int) else None,
                "effective_rank": rank_by_code.get(code),
            })

        return {
            "program_type": engagement.tool,
            "has_scores": any(m["score"] is not None for m in modules),
            "diagnostic_id": str(diagnostic.id) if diagnostic else None,
            "diagnostic_completed_at": diagnostic.completed_at if diagnostic else None,
            "overall_score": float(diagnostic.overall_score)
            if diagnostic and diagnostic.overall_score is not None
            else None,
            "modules": modules,
        }

    def compute_value_movement(self, engagement_id: UUID) -> Dict[str, Any]:
        recent = (
            self.db.query(Diagnostic)
            .filter(
                Diagnostic.engagement_id == engagement_id,
                Diagnostic.status == "completed",
                Diagnostic.is_deleted == False,  # noqa: E712
            )
            .order_by(Diagnostic.completed_at.desc())
            .limit(2)
            .all()
        )
        if len(recent) < 2:
            return {"has_comparison": False}

        current, previous = recent[0], recent[1]
        canonical = ScoringService.VALUE_BUILDER_MODULES

        def module_map(diagnostic: Diagnostic) -> Dict[str, Dict[str, Any]]:
            modules = (diagnostic.module_scores or {}).get("modules", {})
            return modules if isinstance(modules, dict) else {}

        prev_modules = module_map(previous)
        curr_modules = module_map(current)

        movements = []
        for code, name in canonical.items():
            prev_score = (prev_modules.get(code) or {}).get("score")
            curr_score = (curr_modules.get(code) or {}).get("score")
            delta = (curr_score - prev_score) if (prev_score is not None and curr_score is not None) else None
            movements.append({
                "module_code": code,
                "module_name": name,
                "previous_score": prev_score,
                "current_score": curr_score,
                "delta": delta,
                "previous_rag": ScoringService.determine_rag_status(prev_score) if prev_score is not None else None,
                "current_rag": ScoringService.determine_rag_status(curr_score) if curr_score is not None else None,
            })

        prev_overall = float(previous.overall_score) if previous.overall_score is not None else None
        curr_overall = float(current.overall_score) if current.overall_score is not None else None

        return {
            "has_comparison": True,
            "previous_diagnostic_id": str(previous.id),
            "current_diagnostic_id": str(current.id),
            "overall_score_previous": prev_overall,
            "overall_score_current": curr_overall,
            "overall_score_delta": (curr_overall - prev_overall) if (prev_overall is not None and curr_overall is not None) else None,
            "module_movements": movements,
        }


def get_program_guide_service(db: Session) -> ProgramGuideService:
    return ProgramGuideService(db)
