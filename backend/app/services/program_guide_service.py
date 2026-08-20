"""
Program Guide service: composes module card content with the recommended
module order for an engagement, and tracks advisor overrides.

The recommended order is computed live from the latest BBA ("Recommendations
Report Builder") findings for the engagement - never cached - since the
computation is cheap (sorting ~10 in-memory finding objects, no LLM calls).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.bba import BBA
from app.models.diagnostic import Diagnostic
from app.models.engagement import Engagement
from app.models.program_guide import EngagementProgramModuleState, ProgramModuleContent
from app.services.scoring_service import ScoringService

# Bookend stages that aren't ranked business-area modules.
GATEWAY_MODULE_CODE = "M0"
CAPSTONE_MODULE_CODE = "M12"


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
    def _get_latest_bba_with_findings(self, engagement_id: UUID) -> Optional[BBA]:
        """
        Most recently created BBA for this engagement with draft findings -
        same "most recent for this engagement" convention used elsewhere
        (BBAService.get_bbas_by_engagement, diagnostic lookups).
        """
        return (
            self.db.query(BBA)
            .filter(
                BBA.engagement_id == engagement_id,
                BBA.is_deleted == False,  # noqa: E712
                BBA.draft_findings.isnot(None),
            )
            .order_by(BBA.created_at.desc())
            .first()
        )

    # Retired module names, mapped to the code they used to mean.
    #
    # BBA findings are stored as freeform text, so every draft_findings row
    # written before a rename still carries the old wording. The contains
    # fallback below rescues a rename that only widens a name ("People" is a
    # substring of "People & Structure"), but not one that replaces a word:
    # neither "Brand, IP & Competitive Advantage" nor "Brand, IP & Protection"
    # contains the other, so V8 would silently stop matching and its findings
    # would land in unmapped_priority_areas, quietly degrading the recommended
    # order to the default taxonomy.
    #
    # Add an entry here whenever a name in ScoringService.VALUE_BUILDER_MODULES
    # changes. Entries are permanent - the old rows never get rewritten.
    MODULE_NAME_ALIASES = {
        "brand, ip & competitive advantage": "V8",
        "people": "V4",
    }

    @classmethod
    def _match_priority_area_to_module(cls, raw: Optional[str], canonical: Dict[str, str]) -> Optional[str]:
        """
        Map a BBA finding's freeform `priority_area` to a canonical Value
        Builder module code.

        1. Exact case-insensitive match against canonical module names - the
           expected path once BBA's findings prompts are constrained to the
           Value Builder taxonomy.
        2. Exact match against canonical module codes - defensive, in case
           the LLM returns a bare code like "V5".
        3. Exact match against a retired name - see MODULE_NAME_ALIASES. Runs
           before the loose pass so a renamed module resolves to the code it
           was renamed from, not to whichever current name happens to overlap.
        4. Loose "contains" fallback - for BBA rows created before the
           prompt constraint, or any LLM non-compliance.
        """
        if not raw:
            return None
        normalized = raw.strip().lower()
        if not normalized:
            return None

        for code, name in canonical.items():
            if name.lower() == normalized:
                return code

        for code in canonical.keys():
            if code.lower() == normalized:
                return code

        alias = cls.MODULE_NAME_ALIASES.get(normalized)
        if alias and alias in canonical:
            return alias

        for code, name in canonical.items():
            name_lower = name.lower()
            if name_lower in normalized or normalized in name_lower:
                return code

        return None

    def compute_recommended_order(self, engagement: Engagement) -> Dict[str, Any]:
        """
        Compute the recommended M1-M11 (V1-V11) order for an engagement.
        Always returns all 11 module codes - modules BBA didn't rank (or
        that have no BBA yet) are appended in default taxonomy order, so
        the guide is always fully viewable (no gating).
        """
        if engagement.tool != "value_builder":
            return {"source": "unsupported", "order": [], "bba_id": None, "unmapped_priority_areas": []}

        canonical = ScoringService.VALUE_BUILDER_MODULES
        all_codes = list(canonical.keys())

        bba = self._get_latest_bba_with_findings(engagement.id)
        if not bba:
            return {"source": "default", "order": all_codes, "bba_id": None, "unmapped_priority_areas": []}

        findings = sorted(
            (bba.draft_findings or {}).get("findings", []) or [],
            key=lambda f: f.get("rank", 999),
        )

        matched: List[str] = []
        seen = set()
        unmapped: List[str] = []
        for finding in findings:
            raw_area = finding.get("priority_area")
            code = self._match_priority_area_to_module(raw_area, canonical)
            if code and code not in seen:
                matched.append(code)
                seen.add(code)
            elif not code and raw_area:
                unmapped.append(raw_area)

        remaining = [c for c in all_codes if c not in seen]
        return {
            "source": "bba",
            "order": matched + remaining,
            "bba_id": str(bba.id),
            "unmapped_priority_areas": unmapped,
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
                "is_gateway": row.module_code == GATEWAY_MODULE_CODE,
                "is_capstone": row.module_code == CAPSTONE_MODULE_CODE,
            })
        # Order the modules array itself: gateway first, then effective order, capstone last.
        modules.sort(key=lambda m: (
            0 if m["is_gateway"] else (2 if m["is_capstone"] else 1),
            m["effective_rank"] if m["effective_rank"] is not None else m["display_order"],
        ))

        return {
            "program_type": engagement.tool,
            "order_source": effective["source"],
            "source_bba_id": effective.get("bba_id"),
            "unmapped_priority_areas": effective.get("unmapped_priority_areas", []),
            "custom_order_set_at": effective.get("custom_order_set_at"),
            "custom_order_set_by_user_id": effective.get("custom_order_set_by_user_id"),
            "modules": modules,
        }

    def get_dashboard_view(self, engagement: Engagement) -> Dict[str, Any]:
        """
        Progress and the module list - the only Program Guide read an owner gets.

        Built by narrowing get_program_guide_view rather than by a second query,
        so ordering and gateway/capstone handling cannot drift between the two.
        The narrowing is an explicit field list: anything not named here does not
        reach the caller, which is the point.

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
                "is_gateway": m["is_gateway"],
                "is_capstone": m["is_capstone"],
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
    # M12: value movement
    # ------------------------------------------------------------------
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
        Per-module diagnostic state: score, RAG, severity and the BBA findings
        attributed to each module.

        This is the read that compute_value_movement cannot serve. That one is a
        comparison and returns nothing at all below two completed diagnostics,
        which is the ordinary case - most engagements have exactly one. The
        scores are sitting in Diagnostic.module_scores either way; this exposes
        the current position without requiring a prior one to subtract from.

        Findings are attributed with the same matcher that computes the module
        order, so what an advisor reads on a module card is exactly what ranked
        it. Anything that fails to match is returned in unmatched_findings
        rather than dropped - a finding that matched nothing is precisely the
        thing that silently degraded the order.
        """
        canonical = ScoringService.VALUE_BUILDER_MODULES
        if engagement.tool != "value_builder":
            return {
                "program_type": engagement.tool,
                "has_scores": False,
                "has_findings": False,
                "modules": [],
                "unmatched_findings": [],
            }

        diagnostic = self._get_latest_completed_diagnostic(engagement.id)
        raw_modules: Dict[str, Any] = {}
        if diagnostic:
            modules_blob = (diagnostic.module_scores or {}).get("modules")
            if isinstance(modules_blob, dict):
                raw_modules = modules_blob

        bba = self._get_latest_bba_with_findings(engagement.id)
        findings_by_module: Dict[str, List[Dict[str, Any]]] = {}
        unmatched: List[Dict[str, Any]] = []
        if bba:
            findings = sorted(
                (bba.draft_findings or {}).get("findings", []) or [],
                key=lambda f: f.get("rank", 999),
            )
            for finding in findings:
                payload = {
                    "rank": finding.get("rank"),
                    "title": finding.get("title") or "Untitled finding",
                    "summary": finding.get("summary"),
                    "impact": finding.get("impact"),
                    "urgency": finding.get("urgency"),
                    "priority_area": finding.get("priority_area"),
                }
                code = self._match_priority_area_to_module(finding.get("priority_area"), canonical)
                if code:
                    findings_by_module.setdefault(code, []).append(payload)
                else:
                    unmatched.append(payload)

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
                "findings": findings_by_module.get(code, []),
            })

        return {
            "program_type": engagement.tool,
            "has_scores": any(m["score"] is not None for m in modules),
            "has_findings": bool(findings_by_module or unmatched),
            "diagnostic_id": str(diagnostic.id) if diagnostic else None,
            "diagnostic_completed_at": diagnostic.completed_at if diagnostic else None,
            "overall_score": float(diagnostic.overall_score)
            if diagnostic and diagnostic.overall_score is not None
            else None,
            "source_bba_id": str(bba.id) if bba else None,
            "unmatched_findings": unmatched,
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
