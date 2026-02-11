"""
Phase 2 – BBA Excel Task Planner (Engagement Planner) service.

This service:
- Stores advisor/timing context (lead/support advisors, capacity, start month/year)
- Generates structured task rows from the BBA 12‑month plan
- Calculates per‑month BBA hours and capacity warnings

The generated task rows map 1:1 to the Excel columns:
Rec #, Recommendation, Owner, Task, Advisor Hrs, Advisor, Status, Notes, Timing.
"""

from __future__ import annotations

from typing import Dict, Any, List, Tuple
from uuid import UUID
from datetime import datetime
import logging
import re
import calendar

from sqlalchemy.orm import Session

from app.models.bba import BBA
from app.schemas.bba import (
    BBATaskPlannerSettings,
)

logger = logging.getLogger(__name__)


class BBATaskPlannerService:
    """
    Service for Phase 2 – Excel Task Planner built on top of the BBA tool.
    """

    def __init__(self, db: Session):
        self.db = db

    # -------------------------------------------------------------------------
    # Settings persistence
    # -------------------------------------------------------------------------

    def save_settings(
        self,
        bba_id: UUID,
        settings: BBATaskPlannerSettings,
    ) -> BBA:
        """
        Persist task planner settings onto the BBA record.

        These values are reused for all subsequent task generations/exports.
        """
        bba = self._get_bba(bba_id)

        settings_dict = settings.model_dump()
        bba.task_planner_settings = settings_dict
        bba.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(bba)

        logger.info(
            "[BBA Task Planner] Saved settings for BBA %s: %s",
            bba_id,
            settings_dict,
        )
        return bba

    def load_settings(self, bba: BBA) -> BBATaskPlannerSettings:
        """
        Load planner settings from the BBA record.
        Raises ValueError if no settings have been stored yet.
        """
        if not bba.task_planner_settings:
            raise ValueError(
                "Task planner settings have not been configured for this BBA project."
            )
        return BBATaskPlannerSettings.model_validate(bba.task_planner_settings)

    # -------------------------------------------------------------------------
    # Task + summary generation
    # -------------------------------------------------------------------------

    def generate_tasks_and_summary(
        self,
        bba: BBA,
        settings: BBATaskPlannerSettings,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Generate task rows and summary data from a BBA 12‑month plan.

        The algorithm:
        - Uses each recommendation from `bba.twelve_month_plan["recommendations"]`
        - Parses the plan's `timing` field to relative months (e.g. Month 1–3)
        - Maps relative months to real calendar months from start_month/start_year
        - Creates:
          * One Client‑owned task summarising each recommendation
          * One or more BBA‑owned tasks based on the `actions` list
        - Allocates BBA hours per recommendation based on:
          total_monthly_capacity = advisor_count × max_hours_per_month,
          scaled by the recommendation's month span (months_span / 12)
        - Spreads each recommendation's hours evenly across its active months
          to build a per‑month capacity view
        """
        if not bba.twelve_month_plan:
            raise ValueError(
                "12‑month plan is not available. Complete Phase 1 before using the task planner."
            )

        plan = bba.twelve_month_plan or {}
        recommendations = plan.get("recommendations") or []
        if not recommendations:
            raise ValueError(
                "12‑month plan has no recommendations to build tasks from."
            )

        # Pre‑compute recommendation timing ranges and labels
        rec_meta = self._build_recommendation_timing_metadata(
            recommendations=recommendations,
            start_month=settings.start_month,
            start_year=settings.start_year,
        )

        # Combined monthly capacity across all advisors
        monthly_capacity = float(settings.advisor_count * settings.max_hours_per_month)

        tasks: List[Dict[str, Any]] = []
        monthly_hours: Dict[str, float] = {}
        total_bba_hours = 0.0

        for rec, meta in zip(recommendations, rec_meta):
            rec_number = meta["rec_number"]
            recommendation_title = rec.get("title") or f"Recommendation {rec_number}"
            timing_label = meta["timing_label"]
            months_span = meta["months_span"]

            # Approximate total BBA hours for this recommendation.
            # Scale by month span relative to a 12‑month window.
            rec_total_hours = monthly_capacity * (months_span / 12.0)
            total_bba_hours += rec_total_hours

            # Distribute hours evenly across each active month for capacity summary.
            per_month_hours = rec_total_hours / float(months_span)
            for ym_label in meta["ym_labels"]:
                monthly_hours[ym_label] = monthly_hours.get(ym_label, 0.0) + per_month_hours

            # ------------------------------------------------------------------
            # Client task – one summary row per recommendation
            # ------------------------------------------------------------------
            purpose = (rec.get("purpose") or "").strip()
            client_task_text = (
                purpose
                if purpose
                else f"Implement recommendation {rec_number}: {recommendation_title}"
            )

            tasks.append(
                {
                    "rec_number": rec_number,
                    "recommendation": recommendation_title,
                    "owner": "Client",
                    "task": client_task_text,
                    "advisorHrs": 0.0,
                    "advisor": None,
                    "status": "Not yet started",
                    "notes": "",
                    "timing": timing_label,
                }
            )

            # ------------------------------------------------------------------
            # BBA tasks – derived from actions (or a single generic support task)
            # ------------------------------------------------------------------
            actions = rec.get("actions") or []
            bba_actions: List[str] = [
                a.strip() for a in actions if isinstance(a, str) and a.strip()
            ]

            if not bba_actions:
                bba_actions = [
                    f"Support client to implement '{recommendation_title}'",
                ]

            num_bba_tasks = len(bba_actions)
            per_task_hours = rec_total_hours / float(num_bba_tasks) if num_bba_tasks else 0.0

            for idx, action_text in enumerate(bba_actions):
                advisor_name = settings.lead_advisor
                if settings.support_advisor and (idx % 2 == 1):
                    advisor_name = settings.support_advisor

                tasks.append(
                    {
                        "rec_number": rec_number,
                        "recommendation": recommendation_title,
                        "owner": "BBA",
                        "task": action_text,
                        "advisorHrs": round(per_task_hours, 2),
                        "advisor": advisor_name,
                        "status": "Not yet started",
                        "notes": "",
                        "timing": timing_label,
                    }
                )

        # Build summary and capacity warnings
        monthly_capacity_combined = monthly_capacity
        warnings: List[str] = []
        rounded_monthly_hours: Dict[str, float] = {}

        for ym, hours in sorted(monthly_hours.items()):
            rounded = round(hours, 2)
            rounded_monthly_hours[ym] = rounded
            if rounded > monthly_capacity_combined + 1e-6:
                warnings.append(
                    f"Month {ym} is scheduled for {rounded:.1f} BBA hours, "
                    f"which exceeds the configured monthly capacity of {monthly_capacity_combined:.1f} hours."
                )

        summary: Dict[str, Any] = {
            "total_bba_hours": round(total_bba_hours, 2),
            "max_hours_per_month": monthly_capacity_combined,
            "monthly_hours": rounded_monthly_hours,
            "warnings": warnings,
        }

        return tasks, summary

    def save_tasks_and_summary(
        self,
        bba_id: UUID,
        tasks: List[Dict[str, Any]],
        summary: Dict[str, Any],
    ) -> BBA:
        """
        Persist generated tasks and summary to the BBA record.
        """
        bba = self._get_bba(bba_id)
        bba.task_planner_tasks = tasks
        bba.task_planner_summary = summary
        bba.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(bba)

        logger.info(
            "[BBA Task Planner] Saved %d task rows and summary for BBA %s",
            len(tasks),
            bba_id,
        )
        return bba

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_bba(self, bba_id: UUID) -> BBA:
        bba = self.db.query(BBA).filter(BBA.id == bba_id).first()
        if not bba:
            raise ValueError(f"BBA project {bba_id} not found")
        return bba

    def _build_recommendation_timing_metadata(
        self,
        recommendations: List[Dict[str, Any]],
        start_month: int,
        start_year: int,
    ) -> List[Dict[str, Any]]:
        """
        For each recommendation, parse its timing string and map to:
        - rec_number
        - months_span (relative, e.g. Month 1–3 => 3)
        - ym_labels: list of YYYY-MM labels for each active month
        - timing_label: human label for UI/Excel (e.g. 'Nov–Dec 2025')

        If timing cannot be parsed, defaults to Month 1.
        """
        base_index = start_year * 12 + (start_month - 1)
        meta: List[Dict[str, Any]] = []

        for idx, rec in enumerate(recommendations):
            rec_number = rec.get("number") or (idx + 1)
            timing_raw = (rec.get("timing") or "").strip()

            start_rel, end_rel = self._parse_timing_to_relative_months(timing_raw)
            if start_rel is None or end_rel is None:
                start_rel, end_rel = 1, 1  # default to Month 1

            if end_rel < start_rel:
                end_rel = start_rel

            months_span = max(1, end_rel - start_rel + 1)

            # Absolute month indices (0-based across years)
            abs_indices = [
                base_index + (start_rel - 1) + offset for offset in range(months_span)
            ]

            ym_labels = [self._year_month_label_from_index(i) for i in abs_indices]

            # Human timing label for Excel (single month or range)
            if ym_labels:
                start_label_human = self._human_month_label_from_index(abs_indices[0])
                end_label_human = self._human_month_label_from_index(abs_indices[-1])
                timing_label = (
                    start_label_human
                    if start_label_human == end_label_human
                    else f"{start_label_human}–{end_label_human}"
                )
            else:
                timing_label = self._human_month_label_from_index(base_index)

            meta.append(
                {
                    "rec_number": rec_number,
                    "months_span": months_span,
                    "ym_labels": ym_labels,
                    "timing_label": timing_label,
                }
            )

        return meta

    @staticmethod
    def _parse_timing_to_relative_months(
        timing: str,
    ) -> Tuple[int | None, int | None]:
        """
        Parse a timing string such as:
        - "Month 1-3"
        - "Months 4–6"
        - "Month 7"
        - "1-3"

        Returns (start_month, end_month) as 1‑based indices relative to the
        start of the engagement (Month 1).
        """
        if not timing:
            return None, None

        # Extract up to two integers from the string
        numbers = [int(n) for n in re.findall(r"\d+", timing)]
        if not numbers:
            return None, None
        if len(numbers) == 1:
            return numbers[0], numbers[0]
        return numbers[0], numbers[1]

    @staticmethod
    def _year_month_label_from_index(index: int) -> str:
        """
        Convert an absolute month index (year * 12 + month‑0‑based) into
        a canonical YYYY-MM label (e.g. '2025-11').
        """
        year = index // 12
        month = index % 12 + 1
        return f"{year:04d}-{month:02d}"

    @staticmethod
    def _human_month_label_from_index(index: int) -> str:
        """
        Convert an absolute month index into a human label like 'Nov 2025'.
        """
        year = index // 12
        month = index % 12 + 1
        month_abbr = calendar.month_abbr[month]
        return f"{month_abbr} {year}"


def get_bba_task_planner_service(db: Session) -> BBATaskPlannerService:
    """FastAPI dependency factory for the BBA task planner service."""
    return BBATaskPlannerService(db)

