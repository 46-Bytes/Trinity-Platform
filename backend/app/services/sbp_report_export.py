"""
Strategic Business Plan Report Exporter
Generates professional .docx files from the assembled plan.
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from bs4 import BeautifulSoup

from app.models.strategic_business_plan import StrategicBusinessPlan

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "files" / "exports" / "sbp"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class SBPReportExporter:
    """Generates a formatted .docx Strategic Business Plan document."""

    def _add_heading(self, doc: Document, text: str, level: int = 1):
        heading = doc.add_heading(text, level=level)
        for run in heading.runs:
            run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)

    def _html_to_docx(self, doc: Document, html_content: str):
        """Convert HTML content to docx paragraphs."""
        if not html_content:
            return

        soup = BeautifulSoup(html_content, "html.parser")

        for element in soup.children:
            if element.name in ("h1", "h2", "h3", "h4"):
                level_map = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}
                self._add_heading(doc, element.get_text(strip=True), level=level_map.get(element.name, 3))
            elif element.name == "p":
                para = doc.add_paragraph(element.get_text(strip=True))
                para.style.font.size = Pt(11)
            elif element.name in ("ul", "ol"):
                for li in element.find_all("li", recursive=False):
                    para = doc.add_paragraph(li.get_text(strip=True), style="List Bullet")
            elif element.name == "table":
                self._html_table_to_docx(doc, element)
            elif element.name == "blockquote":
                para = doc.add_paragraph(element.get_text(strip=True))
                para.paragraph_format.left_indent = Cm(1.5)
                para.style.font.italic = True
            elif hasattr(element, "get_text"):
                text = element.get_text(strip=True)
                if text:
                    doc.add_paragraph(text)

    def _html_table_to_docx(self, doc: Document, table_element):
        """Convert an HTML table to a docx table."""
        rows_data = []
        for tr in table_element.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
            if cells:
                rows_data.append(cells)

        if not rows_data:
            return

        max_cols = max(len(row) for row in rows_data)
        table = doc.add_table(rows=len(rows_data), cols=max_cols)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        for i, row_data in enumerate(rows_data):
            for j, cell_text in enumerate(row_data):
                if j < max_cols:
                    cell = table.cell(i, j)
                    cell.text = cell_text
                    # Bold header row
                    if i == 0:
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs:
                                run.bold = True

        doc.add_paragraph("")  # Spacing after table

    def generate_docx(self, plan: StrategicBusinessPlan) -> Path:
        """Generate the main Strategic Business Plan .docx document."""
        doc = Document()

        # Set default font
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Calibri"
        font.size = Pt(11)

        # Title page
        doc.add_paragraph("")
        doc.add_paragraph("")
        title = doc.add_heading("Strategic Business Plan", level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        subtitle = doc.add_paragraph()
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = subtitle.add_run(plan.client_name or "Client")
        run.font.size = Pt(18)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

        meta = doc.add_paragraph()
        meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
        year = datetime.now().year
        horizon = plan.planning_horizon or "3-year"
        meta_run = meta.add_run(f"{horizon} Plan | {year}")
        meta_run.font.size = Pt(14)
        meta_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        if plan.target_audience:
            audience = doc.add_paragraph()
            audience.alignment = WD_ALIGN_PARAGRAPH.CENTER
            aud_run = audience.add_run(f"Prepared for: {plan.target_audience}")
            aud_run.font.size = Pt(12)
            aud_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        doc.add_page_break()

        # Table of Contents header
        self._add_heading(doc, "Table of Contents", level=1)
        final_plan = plan.final_plan or {}
        sections = final_plan.get("sections", [])
        for i, section in enumerate(sections):
            if section.get("content"):
                para = doc.add_paragraph(f"{i + 1}. {section['title']}")
                para.paragraph_format.space_before = Pt(2)
                para.paragraph_format.space_after = Pt(2)

        doc.add_page_break()

        # Sections
        for i, section in enumerate(sections):
            if not section.get("content"):
                continue

            self._add_heading(doc, f"{i + 1}. {section['title']}", level=1)
            self._html_to_docx(doc, section["content"])

            if section.get("strategic_implications"):
                self._add_heading(doc, "Strategic Implications", level=2)
                self._html_to_docx(doc, section["strategic_implications"])

            doc.add_page_break()

        # Footer / Confidentiality
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run("CONFIDENTIAL")
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

        # Save
        client_safe = (plan.client_name or "Client").replace(" ", "_")
        filename = f"Strategic_Business_Plan_{client_safe}_{datetime.now().year}.docx"
        output_path = OUTPUT_DIR / filename
        doc.save(str(output_path))
        logger.info(f"Generated SBP report: {output_path}")

        # Update plan record
        plan.generated_report_path = str(output_path)
        plan.status = "completed"
        plan.completed_at = datetime.now()

        return output_path


class SBPEmployeeExporter(SBPReportExporter):
    """Generates an employee-facing strategy document variant."""

    def generate_employee_docx(self, plan: StrategicBusinessPlan) -> Path:
        doc = Document()

        style = doc.styles["Normal"]
        style.font.name = "Calibri"
        style.font.size = Pt(11)

        # Title
        title = doc.add_heading("Our Strategic Direction", level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        subtitle = doc.add_paragraph()
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = subtitle.add_run(plan.client_name or "Our Company")
        run.font.size = Pt(16)

        doc.add_page_break()

        # Include select sections suitable for employees
        final_plan = plan.final_plan or {}
        sections = final_plan.get("sections", [])

        employee_keys = [
            "executive_summary",
            "strategic_intent",
            "growth_opportunities",
            "strategic_priorities",
            "implementation_roadmap",
        ]

        for section in sections:
            if section["key"] in employee_keys and section.get("content"):
                self._add_heading(doc, section["title"], level=1)
                self._html_to_docx(doc, section["content"])
                doc.add_page_break()

        # Save
        client_safe = (plan.client_name or "Client").replace(" ", "_")
        filename = f"Employee_Strategy_Document_{client_safe}_{datetime.now().year}.docx"
        output_path = OUTPUT_DIR / filename
        doc.save(str(output_path))
        logger.info(f"Generated employee strategy document: {output_path}")

        plan.generated_employee_report_path = str(output_path)
        return output_path


def get_sbp_report_exporter() -> SBPReportExporter:
    return SBPReportExporter()


def get_sbp_employee_exporter() -> SBPEmployeeExporter:
    return SBPEmployeeExporter()
