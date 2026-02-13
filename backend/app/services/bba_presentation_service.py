"""
Phase 3 – BBA PowerPoint Presentation Generator service.

This service:
- Generates structured slide content via OpenAI from the BBA diagnostic report data
- Persists the full slide deck to bba.presentation_slides
- Supports per-slide editing
"""

from __future__ import annotations

from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime
import json
import logging

from sqlalchemy.orm import Session

from app.models.bba import BBA
from app.services.openai_service import OpenAIService
from app.services.bba_conversation_engine import load_bba_prompt

logger = logging.getLogger(__name__)


class BBAPresentationService:
    """
    Service for Phase 3 – PowerPoint Presentation built on top of the BBA tool.

    Uses OpenAI to generate concise, spoken-delivery slide content from the
    diagnostic report, then persists and allows per-slide editing.
    """

    def __init__(self, db: Session, openai_service: OpenAIService | None = None):
        self.db = db
        self.openai_service = openai_service or OpenAIService()

    # -------------------------------------------------------------------------
    # Slide generation (AI-driven)
    # -------------------------------------------------------------------------

    async def generate_slides(self, bba: BBA) -> List[Dict[str, Any]]:
        """
        Generate all presentation slides via OpenAI.

        Uses the BBA diagnostic data (executive summary, expanded findings,
        snapshot table, 12-month plan) to produce structured slide content.
        """
        # Validate required data
        if not bba.twelve_month_plan:
            raise ValueError(
                "12-month plan is not available. Complete Phase 1 before generating the presentation."
            )

        # Load prompts
        try:
            system_prompt = load_bba_prompt("bba_system_prompt")
            step_prompt = load_bba_prompt("phase3_presentation")
        except FileNotFoundError as e:
            logger.error("[BBA Presentation] Failed to load prompts: %s", e)
            raise

        system_content = f"{system_prompt}\n\n{step_prompt}"

        # Build user content with full report context
        user_content = self._build_user_content(bba)

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        try:
            logger.info("[BBA Presentation] Calling OpenAI for slide generation...")
            result = await self.openai_service.generate_json_completion(
                messages=messages,
                reasoning_effort="medium",
            )

            parsed = result.get("parsed_content", {})
            slides = parsed.get("slides", [])

            if not slides:
                logger.warning(
                    "[BBA Presentation] AI returned no slides; parsed_content keys: %s",
                    list(parsed.keys()),
                )
                raise ValueError("AI did not return any slides. Please try again.")

            # Ensure every slide has an index and approved=false
            for i, slide in enumerate(slides):
                slide["index"] = i
                slide.setdefault("approved", False)

            logger.info(
                "[BBA Presentation] AI generated %d slides (tokens: %s)",
                len(slides),
                result.get("tokens_used", "?"),
            )

            return slides

        except Exception as e:
            logger.error(
                "[BBA Presentation] Failed to generate slides via AI: %s",
                str(e),
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def save_slides(self, bba_id: UUID, slides: List[Dict[str, Any]]) -> BBA:
        """Persist generated slides to the BBA record."""
        bba = self._get_bba(bba_id)
        bba.presentation_slides = {"slides": slides}
        bba.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(bba)

        logger.info(
            "[BBA Presentation] Saved %d slides for BBA %s",
            len(slides),
            bba_id,
        )
        return bba

    def update_slide(
        self,
        bba_id: UUID,
        slide_index: int,
        updates: Dict[str, Any],
    ) -> BBA:
        """
        Update a single slide in the presentation_slides JSONB array.

        Only non-None fields in `updates` are merged into the existing slide.
        """
        bba = self._get_bba(bba_id)

        if not bba.presentation_slides or not bba.presentation_slides.get("slides"):
            raise ValueError("No presentation slides exist yet. Generate slides first.")

        slides = bba.presentation_slides["slides"]

        if slide_index < 0 or slide_index >= len(slides):
            raise ValueError(
                f"Slide index {slide_index} is out of range (0–{len(slides) - 1})."
            )

        # Merge only non-None updates
        for key, value in updates.items():
            if value is not None:
                slides[slide_index][key] = value

        # Force SQLAlchemy to detect the JSONB mutation
        bba.presentation_slides = {**bba.presentation_slides, "slides": slides}
        bba.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(bba)

        logger.info(
            "[BBA Presentation] Updated slide %d for BBA %s",
            slide_index,
            bba_id,
        )
        return bba

    def delete_slide(
        self,
        bba_id: UUID,
        slide_index: int,
    ) -> BBA:
        """
        Delete a single slide from the presentation_slides JSONB array and
        reindex the remaining slides.
        """
        bba = self._get_bba(bba_id)

        if not bba.presentation_slides or not bba.presentation_slides.get("slides"):
            raise ValueError("No presentation slides exist yet. Generate slides first.")

        slides = bba.presentation_slides["slides"]

        if slide_index < 0 or slide_index >= len(slides):
            raise ValueError(
                f"Slide index {slide_index} is out of range (0–{len(slides) - 1})."
            )

        # Remove the requested slide
        removed = slides.pop(slide_index)
        logger.info(
            "[BBA Presentation] Deleting slide %d for BBA %s (title=%s)",
            slide_index,
            bba_id,
            removed.get("title"),
        )

        # Reindex remaining slides so their `index` fields stay in sync
        for i, slide in enumerate(slides):
            slide["index"] = i

        bba.presentation_slides = {**bba.presentation_slides, "slides": slides}
        bba.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(bba)

        logger.info(
            "[BBA Presentation] Deleted slide %d for BBA %s; %d slides remain",
            slide_index,
            bba_id,
            len(slides),
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

    def _build_user_content(self, bba: BBA) -> str:
        """
        Assemble the user-message content for the AI call, including all
        diagnostic report sections.
        """
        plan = bba.twelve_month_plan or {}
        recommendations = plan.get("recommendations") or []

        # Executive summary
        exec_summary = bba.executive_summary or "Not available."

        # Expanded findings
        expanded = bba.expanded_findings or {}
        expanded_list = expanded.get("expanded_findings") or []

        # Snapshot table
        snapshot = bba.snapshot_table or {}
        snapshot_rows = snapshot.get("rows") or []

        # Timeline from the plan
        timeline_summary = plan.get("timeline_summary") or {}
        timeline_rows = timeline_summary.get("rows") or []

        sections = [
            "Generate the presentation slides for this diagnostic report.",
            "",
            "## Client Context",
            f"- Client Name: {bba.client_name or 'Unknown'}",
            f"- Industry: {bba.industry or 'Unknown'}",
            f"- Strategic Priorities: {bba.strategic_priorities or 'Not specified'}",
            "",
            "## Executive Summary",
            exec_summary,
            "",
            "## Expanded Findings",
            json.dumps(expanded_list, indent=2) if expanded_list else "Not available.",
            "",
            "## Snapshot Table",
            json.dumps(snapshot_rows, indent=2) if snapshot_rows else "Not available.",
            "",
            "## 12-Month Plan Recommendations",
            json.dumps(recommendations, indent=2) if recommendations else "Not available.",
            "",
            "## Timeline Summary",
            json.dumps(timeline_rows, indent=2) if timeline_rows else "Not available.",
            "",
            "## Instructions",
            "Generate slides following the schema described in the system prompt.",
            f"The title slide subtitle should read: \"{bba.client_name or 'Client'} | {self._current_month_year()}\"",
            "Return ONLY the JSON object with the slides array.",
        ]

        return "\n".join(sections)

    @staticmethod
    def _current_month_year() -> str:
        """Return current month and year, e.g. 'February 2026'."""
        now = datetime.utcnow()
        import calendar
        return f"{calendar.month_name[now.month]} {now.year}"


def get_bba_presentation_service(
    db: Session,
    openai_service: OpenAIService | None = None,
) -> BBAPresentationService:
    """FastAPI dependency factory for the BBA presentation service."""
    return BBAPresentationService(db, openai_service)
