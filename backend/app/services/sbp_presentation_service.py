"""
Strategic Business Plan Presentation Service
Generates slide content from the assembled plan.
"""
import json
import logging
from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.services.claude_service import ClaudeService
from app.services.sbp_service import get_sbp_service

logger = logging.getLogger(__name__)


class SBPPresentationService:
    """Generates presentation slides from the Strategic Business Plan."""

    def __init__(self, db: Session):
        self.db = db
        self.claude_service = ClaudeService()
        self.sbp_service = get_sbp_service(db)

    async def generate_slides(self, plan_id: UUID) -> List[Dict[str, Any]]:
        plan = self.sbp_service.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        if not plan.final_plan:
            raise ValueError("Plan must be assembled before generating presentation")

        sections = plan.final_plan.get("sections", [])
        client_name = plan.client_name or "Client"

        system_prompt = """You are a presentation designer creating slides for a Strategic Business Plan.
Create clear, concise slides suitable for a management presentation.
Return a JSON array of slide objects."""

        section_summaries = []
        for s in sections:
            if s.get("content"):
                section_summaries.append(f"## {s['title']}\n{s['content'][:500]}...")

        user_prompt = f"""Create a presentation for the Strategic Business Plan of {client_name}.

Plan sections:
{"".join(section_summaries)}

Return a JSON array of slides:
[
  {{"index": 0, "type": "title", "title": "Strategic Business Plan", "subtitle": "{client_name}", "bullets": null, "rows": null, "approved": false}},
  {{"index": 1, "type": "section_overview", "title": "...", "subtitle": null, "bullets": ["..."], "rows": null, "approved": false}},
  ...
]

Create 8-12 slides covering the key strategic points. Keep bullets concise (max 6 per slide)."""

        try:
            response = self.claude_service.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            response_text = response.content[0].text

            try:
                slides = json.loads(response_text)
            except json.JSONDecodeError:
                slides = [
                    {"index": 0, "type": "title", "title": "Strategic Business Plan", "subtitle": client_name, "bullets": None, "rows": None, "approved": False},
                ]

            # Save to plan
            plan.presentation_slides = {"slides": slides}
            flag_modified(plan, "presentation_slides")
            self.db.commit()
            self.db.refresh(plan)

            return slides
        except Exception as e:
            logger.error(f"Presentation generation failed: {e}", exc_info=True)
            raise


def get_sbp_presentation_service(db: Session) -> SBPPresentationService:
    return SBPPresentationService(db)
