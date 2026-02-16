"""
Phase 2 – BBA Excel Task Planner (Engagement Planner) service.

This service:
- Stores advisor/timing context (lead/support advisors, capacity, start month/year)
- Generates structured task rows via OpenAI from the BBA 12-month plan

The generated task rows map 1:1 to the Excel columns:
Rec #, Recommendation, Owner, Task, Advisor Hrs, Advisor, Status, Notes, Timing.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from datetime import datetime
import json
import logging
import re
import calendar

from sqlalchemy.orm import Session

from app.models.bba import BBA
from app.schemas.bba import (
    BBATaskPlannerSettings,
)
from app.services.openai_service import OpenAIService
from app.services.bba_conversation_engine import load_bba_prompt

logger = logging.getLogger(__name__)


class BBATaskPlannerService:
    """
    Service for Phase 2 – Excel Task Planner built on top of the BBA tool.

    Uses OpenAI to generate focused, practical task rows from the 12-month plan,
    then applies deterministic post-processing for hour summaries and capacity
    warnings.
    """

    def __init__(self, db: Session, openai_service: OpenAIService | None = None):
        self.db = db
        self.openai_service = openai_service or OpenAIService()

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
    # Task generation (AI-driven); no capacity summary
    # -------------------------------------------------------------------------

    async def generate_tasks_and_summary(
        self,
        bba: BBA,
        settings: BBATaskPlannerSettings,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Generate task rows via OpenAI. No capacity summary is computed.

        Flow:
        1. Build timing metadata for each recommendation
        2. Construct AI prompt with full context
        3. Call OpenAI to generate focused task rows
        """
        if not bba.twelve_month_plan:
            raise ValueError(
                "12-month plan is not available. Complete Phase 1 before using the task planner."
            )

        plan = bba.twelve_month_plan or {}
        recommendations = plan.get("recommendations") or []
        if not recommendations:
            raise ValueError(
                "12-month plan has no recommendations to build tasks from."
            )

        # Pre-compute recommendation timing ranges and labels
        rec_meta = self._build_recommendation_timing_metadata(
            recommendations=recommendations,
            start_month=settings.start_month,
            start_year=settings.start_year,
        )

        # Combined monthly capacity across all advisors (for AI context only)
        monthly_capacity = float(settings.advisor_count * settings.max_hours_per_month)

        # Build per-recommendation context for the AI (including allocated hours)
        # Allocated hours = total BBA capacity during this recommendation's time window
        # (monthly_capacity × months_span), not a fraction of one month
        rec_context = []
        for rec, meta in zip(recommendations, rec_meta):
            months_span = meta["months_span"]
            rec_total_hours = round(monthly_capacity * months_span, 2)

            rec_context.append({
                "rec_number": meta["rec_number"],
                "title": rec.get("title") or f"Recommendation {meta['rec_number']}",
                "timing_label": meta["timing_label"],
                "months_span": months_span,
                "allocated_bba_hours": rec_total_hours,
                "purpose": rec.get("purpose", ""),
                "key_objectives": rec.get("key_objectives", []),
                "actions": rec.get("actions", []),
                "bba_support": rec.get("bba_support", ""),
                "expected_outcomes": rec.get("expected_outcomes", []),
            })

        # --- Call OpenAI ---
        tasks = await self._generate_tasks_via_ai(
            bba=bba,
            settings=settings,
            rec_context=rec_context,
        )

        return tasks, None

    async def _generate_tasks_via_ai(
        self,
        bba: BBA,
        settings: BBATaskPlannerSettings,
        rec_context: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Call OpenAI to generate focused task rows from the 12-month plan.
        """
        # Load prompts
        try:
            system_prompt = load_bba_prompt("bba_system_prompt")
            step_prompt = load_bba_prompt("phase2_task_generation")
        except FileNotFoundError as e:
            logger.error("[BBA Task Planner] Failed to load prompts: %s", e)
            raise

        system_content = f"{system_prompt}\n\n{step_prompt}"

        # Build user content with full context
        user_content = f"""Generate the advisor task list for this engagement.

## Client Context
- Client Name: {bba.client_name or 'Unknown'}
- Industry: {bba.industry or 'Unknown'}
- Strategic Priorities: {bba.strategic_priorities or 'Not specified'}

## Engagement Settings
- Lead Advisor: {settings.lead_advisor}
- Support Advisor: {settings.support_advisor or 'None'}
- Total Advisors: {settings.advisor_count}
- Maximum Hours per Month (combined): {settings.advisor_count * settings.max_hours_per_month}
- Engagement Start: {calendar.month_name[settings.start_month]} {settings.start_year}

## Recommendations (from 12-Month Plan)

{json.dumps(rec_context, indent=2)}

## Instructions

For each recommendation above, generate:
- 1 Client-owned task (owner="Client", advisorHrs=0, advisor=null)
- 1 to 3 BBA-owned tasks (owner="BBA") with hours summing to the `allocated_bba_hours` for that recommendation
- Use the `timing_label` as the `timing` value
- Assign "{settings.lead_advisor}" as the primary advisor; assign "{settings.support_advisor or settings.lead_advisor}" to secondary tasks where appropriate

Return ONLY a JSON object with a "tasks" key containing the array of task rows.
"""

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        try:
            logger.info("[BBA Task Planner] Calling OpenAI for task generation...")
            result = await self.openai_service.generate_json_completion(
                messages=messages,
                reasoning_effort="medium",
            )

            parsed = result.get("parsed_content", {})
            tasks = parsed.get("tasks", [])

            if not tasks:
                logger.warning(
                    "[BBA Task Planner] AI returned no tasks; parsed_content keys: %s",
                    list(parsed.keys()),
                )
                raise ValueError("AI did not return any tasks. Please try again.")

            logger.info(
                "[BBA Task Planner] AI generated %d task rows (tokens: %s)",
                len(tasks),
                result.get("tokens_used", "?"),
            )

            return tasks

        except Exception as e:
            logger.error(
                "[BBA Task Planner] Failed to generate tasks via AI: %s",
                str(e),
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def save_tasks_and_summary(
        self,
        bba_id: UUID,
        tasks: List[Dict[str, Any]],
        summary: Dict[str, Any] | None = None,
    ) -> BBA:
        """
        Persist generated tasks to the BBA record. Summary is no longer used.
        """
        bba = self._get_bba(bba_id)
        bba.task_planner_tasks = tasks
        bba.task_planner_summary = None  # Phase 2 no longer produces capacity summary
        bba.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(bba)

        logger.info(
            "[BBA Task Planner] Saved %d task rows for BBA %s",
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
        - months_span (relative, e.g. Month 1-3 => 3)
        - ym_labels: list of YYYY-MM labels for each active month
        - timing_label: human label for UI/Excel (e.g. 'Nov-Dec 2025')

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
                    else f"{start_label_human}\u2013{end_label_human}"
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
        - "Months 4-6"
        - "Month 7"
        - "1-3"

        Returns (start_month, end_month) as 1-based indices relative to the
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
        Convert an absolute month index (year * 12 + month-0-based) into
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


def get_bba_task_planner_service(
    db: Session,
    openai_service: OpenAIService | None = None,
) -> BBATaskPlannerService:
    """FastAPI dependency factory for the BBA task planner service."""
    return BBATaskPlannerService(db, openai_service)
