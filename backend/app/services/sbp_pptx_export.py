"""
Strategic Business Plan PowerPoint Exporter
Generates .pptx files from generated slide content.
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

from app.models.strategic_business_plan import StrategicBusinessPlan

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "files" / "exports" / "sbp"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class SBPPptxExporter:
    """Generates a .pptx presentation from the plan's slide content."""

    def generate_pptx(self, plan: StrategicBusinessPlan) -> Path:
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        slides_data = []
        if plan.presentation_slides and isinstance(plan.presentation_slides, dict):
            slides_data = plan.presentation_slides.get("slides", [])

        for slide_data in slides_data:
            slide_type = slide_data.get("type", "section_overview")

            if slide_type == "title":
                self._add_title_slide(prs, slide_data, plan)
            else:
                self._add_content_slide(prs, slide_data)

        # Save
        client_safe = (plan.client_name or "Client").replace(" ", "_")
        filename = f"Strategic_Business_Plan_Presentation_{client_safe}.pptx"
        output_path = OUTPUT_DIR / filename
        prs.save(str(output_path))
        logger.info(f"Generated SBP presentation: {output_path}")
        return output_path

    def _add_title_slide(self, prs: Presentation, data: Dict[str, Any], plan: StrategicBusinessPlan):
        layout = prs.slide_layouts[0]  # Title slide
        slide = prs.slides.add_slide(layout)

        if slide.placeholders[0]:
            slide.placeholders[0].text = data.get("title", "Strategic Business Plan")
        if len(slide.placeholders) > 1 and slide.placeholders[1]:
            subtitle = data.get("subtitle", plan.client_name or "")
            slide.placeholders[1].text = subtitle

    def _add_content_slide(self, prs: Presentation, data: Dict[str, Any]):
        layout = prs.slide_layouts[1]  # Title and Content
        slide = prs.slides.add_slide(layout)

        if slide.placeholders[0]:
            slide.placeholders[0].text = data.get("title", "")

        bullets = data.get("bullets", [])
        if bullets and len(slide.placeholders) > 1:
            tf = slide.placeholders[1].text_frame
            tf.clear()
            for i, bullet in enumerate(bullets):
                if i == 0:
                    tf.paragraphs[0].text = bullet
                else:
                    p = tf.add_paragraph()
                    p.text = bullet
                    p.level = 0


def get_sbp_pptx_exporter() -> SBPPptxExporter:
    return SBPPptxExporter()
