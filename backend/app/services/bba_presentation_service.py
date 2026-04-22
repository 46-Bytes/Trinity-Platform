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
from datetime import datetime, timezone
import json
import logging

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.bba import BBA
# from app.services.openai_service import OpenAIService  # Preserved for rollback
from app.services.claude_service import ClaudeService
from app.services.bba_conversation_engine import load_bba_prompt

logger = logging.getLogger(__name__)


class BBAPresentationService:
    """
    Service for Phase 3 – PowerPoint Presentation built on top of the BBA tool.

    Uses OpenAI to generate concise, spoken-delivery slide content from the
    diagnostic report, then persists and allows per-slide editing.
    """

    def __init__(self, db: Session, openai_service: ClaudeService | None = None):
        self.db = db
        self.openai_service = openai_service or ClaudeService()

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
        bba.updated_at = datetime.now(timezone.utc)

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

        # Build new slide dict with merged updates (so JSONB change is detected)
        merged = dict(slides[slide_index])
        for key, value in updates.items():
            if value is not None:
                merged[key] = value

        new_slides = list(slides)
        new_slides[slide_index] = merged
        bba.presentation_slides = {**bba.presentation_slides, "slides": new_slides}
        flag_modified(bba, "presentation_slides")
        bba.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(bba)

        logger.info(
            "[BBA Presentation] Updated slide %d for BBA %s",
            slide_index,
            bba_id,
        )
        return bba

    def add_slide(
        self,
        bba_id: UUID,
        slide_data: Dict[str, Any],
    ) -> BBA:
        """
        Add a new slide to the presentation_slides JSONB array.

        The slide is appended at the end and assigned the next index.
        """
        bba = self._get_bba(bba_id)

        if not bba.presentation_slides or not bba.presentation_slides.get("slides"):
            raise ValueError("No presentation slides exist yet. Generate slides first.")

        slides = list(bba.presentation_slides["slides"])
        new_index = len(slides)

        # Build the new slide with defaults
        new_slide = {
            "index": new_index,
            "type": slide_data.get("type", "recommendation"),
            "title": slide_data.get("title", ""),
            "subtitle": slide_data.get("subtitle"),
            "bullets": slide_data.get("bullets"),
            "finding": slide_data.get("finding"),
            "recommendation_bullets": slide_data.get("recommendation_bullets"),
            "outcome": slide_data.get("outcome"),
            "rows": slide_data.get("rows"),
            "approved": False,
        }

        slides.append(new_slide)
        bba.presentation_slides = {**bba.presentation_slides, "slides": slides}
        flag_modified(bba, "presentation_slides")
        bba.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(bba)

        logger.info(
            "[BBA Presentation] Added slide %d for BBA %s (title=%s)",
            new_index,
            bba_id,
            new_slide.get("title"),
        )
        return bba

    def move_slide(
        self,
        bba_id: UUID,
        from_index: int,
        to_index: int,
    ) -> BBA:
        """
        Move a slide from one position to another and reindex all slides.
        """
        bba = self._get_bba(bba_id)

        if not bba.presentation_slides or not bba.presentation_slides.get("slides"):
            raise ValueError("No presentation slides exist yet. Generate slides first.")

        slides = list(bba.presentation_slides["slides"])

        if from_index < 0 or from_index >= len(slides):
            raise ValueError(f"Source index {from_index} is out of range (0–{len(slides) - 1}).")
        if to_index < 0 or to_index >= len(slides):
            raise ValueError(f"Target index {to_index} is out of range (0–{len(slides) - 1}).")

        # Remove from old position and insert at new position
        slide = slides.pop(from_index)
        slides.insert(to_index, slide)

        # Reindex
        for i, s in enumerate(slides):
            s = dict(s)
            s["index"] = i
            slides[i] = s

        bba.presentation_slides = {**bba.presentation_slides, "slides": slides}
        flag_modified(bba, "presentation_slides")
        bba.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(bba)

        logger.info(
            "[BBA Presentation] Moved slide %d → %d for BBA %s",
            from_index,
            to_index,
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

        removed = slides[slide_index]
        logger.info(
            "[BBA Presentation] Deleting slide %d for BBA %s (title=%s)",
            slide_index,
            bba_id,
            removed.get("title"),
        )

        # New list without the removed slide; reindex so `index` stays in sync
        new_slides = [s for i, s in enumerate(slides) if i != slide_index]
        for i, slide in enumerate(new_slides):
            slide = dict(slide)
            slide["index"] = i
            new_slides[i] = slide

        bba.presentation_slides = {**bba.presentation_slides, "slides": new_slides}
        flag_modified(bba, "presentation_slides")
        bba.updated_at = datetime.now(timezone.utc)

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
        now = datetime.now(timezone.utc)
        import calendar
        return f"{calendar.month_name[now.month]} {now.year}"


def get_bba_presentation_service(
    db: Session,
    openai_service: ClaudeService | None = None,
) -> BBAPresentationService:
    """FastAPI dependency factory for the BBA presentation service."""
    return BBAPresentationService(db, openai_service)
