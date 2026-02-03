"""
BBA Report Export Service
Generates Word documents from BBA report data using python-docx
"""
from typing import Optional
from datetime import datetime
import io
import logging

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.style import WD_STYLE_TYPE
    from docx.enum.table import WD_TABLE_ALIGNMENT
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from app.models.bba import BBA

logger = logging.getLogger(__name__)


class BBAReportExporter:
    """
    Exports BBA diagnostic reports to Word document format.
    
    Creates professional reports following BBA's house style with:
    - Title page
    - Executive summary
    - Key findings & recommendations snapshot table
    - Key findings ranked by importance
    - 12-month recommendations plan
    - Timeline summary
    """
    
    def __init__(self):
        if not DOCX_AVAILABLE:
            raise ImportError(
                "python-docx is required for Word export. "
                "Install it with: pip install python-docx"
            )
    
    def generate_report(self, bba: BBA) -> bytes:
        """
        Generate a Word document from BBA data.
        
        Args:
            bba: BBA model with all report data
            
        Returns:
            Bytes of the generated Word document
        """
        logger.info(f"[BBA Export] Generating Word report for BBA {bba.id}")
        
        # Create document
        doc = Document()
        
        # Set up styles
        self._setup_styles(doc)
        
        # Add content
        self._add_title_page(doc, bba)
        self._add_page_break(doc)
        
        if bba.executive_summary:
            self._add_executive_summary(doc, bba)
        
        if bba.snapshot_table:
            self._add_snapshot_table(doc, bba)
        
        if bba.expanded_findings:
            self._add_key_findings(doc, bba)
        
        if bba.twelve_month_plan:
            self._add_recommendations_plan(doc, bba)
        
        # Add footer
        self._add_footer(doc, bba)
        
        # Save to bytes
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        logger.info(f"[BBA Export] Word report generated successfully")
        return buffer.getvalue()
    
    def _setup_styles(self, doc: Document):
        """Set up document styles."""
        # Modify Normal style
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)
        
        # Heading 1 style
        h1_style = doc.styles['Heading 1']
        h1_style.font.name = 'Calibri'
        h1_style.font.size = Pt(16)
        h1_style.font.bold = True
        h1_style.font.color.rgb = RGBColor(0x1a, 0x36, 0x5d)  # Dark blue
        
        # Heading 2 style
        h2_style = doc.styles['Heading 2']
        h2_style.font.name = 'Calibri'
        h2_style.font.size = Pt(14)
        h2_style.font.bold = True
        h2_style.font.color.rgb = RGBColor(0x1a, 0x36, 0x5d)
        
        # Heading 3 style
        h3_style = doc.styles['Heading 3']
        h3_style.font.name = 'Calibri'
        h3_style.font.size = Pt(12)
        h3_style.font.bold = True
    
    def _add_page_break(self, doc: Document):
        """Add a page break."""
        doc.add_page_break()
    
    def _add_title_page(self, doc: Document, bba: BBA):
        """Add the title page."""
        # Add spacing at top
        for _ in range(8):
            doc.add_paragraph()
        
        # Title
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title.add_run("Diagnostic Findings & Recommendations Report")
        run.bold = True
        run.font.size = Pt(24)
        run.font.color.rgb = RGBColor(0x1a, 0x36, 0x5d)
        
        # Spacing
        doc.add_paragraph()
        doc.add_paragraph()
        
        # Client name
        client = doc.add_paragraph()
        client.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = client.add_run(bba.client_name or "Client")
        run.font.size = Pt(18)
        
        # Date
        doc.add_paragraph()
        date_para = doc.add_paragraph()
        date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_str = datetime.utcnow().strftime("%B %Y")
        date_para.add_run(date_str)
        
        # Spacing
        for _ in range(10):
            doc.add_paragraph()
        
        # Prepared by
        prepared = doc.add_paragraph()
        prepared.alignment = WD_ALIGN_PARAGRAPH.CENTER
        prepared.add_run("Prepared by Benchmark Business Advisory")
    
    def _add_executive_summary(self, doc: Document, bba: BBA):
        """Add the executive summary section."""
        doc.add_heading("Executive Summary", level=1)
        
        if bba.executive_summary:
            # Split into paragraphs and add each
            paragraphs = bba.executive_summary.split('\n\n')
            for para_text in paragraphs:
                if para_text.strip():
                    doc.add_paragraph(para_text.strip())
        
        self._add_page_break(doc)
    
    def _add_snapshot_table(self, doc: Document, bba: BBA):
        """Add the Key Findings & Recommendations Snapshot table."""
        doc.add_heading("Key Findings & Recommendations Snapshot", level=1)
        
        snapshot = bba.snapshot_table
        if not snapshot:
            return
        
        rows_data = snapshot.get('rows', [])
        if not rows_data:
            return
        
        # Create table
        table = doc.add_table(rows=1, cols=4)
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # Header row
        header_cells = table.rows[0].cells
        headers = ['#', 'Priority Area', 'Key Finding', 'Recommendation']
        for i, header in enumerate(headers):
            header_cells[i].text = header
            header_cells[i].paragraphs[0].runs[0].bold = True
            # Set background color for header
            from docx.oxml.ns import nsdecls
            from docx.oxml import parse_xml
            shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="1a365d"/>')
            header_cells[i]._tc.get_or_add_tcPr().append(shading)
            header_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        
        # Data rows
        for row_data in rows_data:
            row = table.add_row()
            row.cells[0].text = str(row_data.get('rank', ''))
            row.cells[1].text = row_data.get('priority_area', '')
            row.cells[2].text = row_data.get('key_finding', '')
            row.cells[3].text = row_data.get('recommendation', '')
        
        # Set column widths
        widths = [Inches(0.4), Inches(1.2), Inches(2.7), Inches(2.7)]
        for row in table.rows:
            for i, cell in enumerate(row.cells):
                cell.width = widths[i]
        
        doc.add_paragraph()  # Spacing
        self._add_page_break(doc)
    
    def _add_key_findings(self, doc: Document, bba: BBA):
        """Add the Key Findings section."""
        doc.add_heading("Key Findings – Ranked by Importance", level=1)
        
        findings = bba.expanded_findings
        if not findings:
            return
        
        findings_list = findings.get('expanded_findings', [])
        
        for finding in findings_list:
            # Finding heading
            rank = finding.get('rank', '')
            title = finding.get('title', '')
            doc.add_heading(f"{rank}. {title}", level=2)
            
            # Priority area
            priority = finding.get('priority_area', '')
            if priority:
                para = doc.add_paragraph()
                run = para.add_run(f"Priority Area: {priority}")
                run.italic = True
            
            # Paragraphs
            paragraphs = finding.get('paragraphs', [])
            for para_text in paragraphs:
                if para_text:
                    doc.add_paragraph(para_text)
            
            # Key points
            key_points = finding.get('key_points', [])
            if key_points:
                doc.add_paragraph()
                for point in key_points:
                    doc.add_paragraph(point, style='List Bullet')
            
            doc.add_paragraph()  # Spacing between findings
        
        self._add_page_break(doc)
    
    def _add_recommendations_plan(self, doc: Document, bba: BBA):
        """Add the 12-Month Recommendations Plan section."""
        doc.add_heading("12-Month Recommendations Plan", level=1)
        
        plan = bba.twelve_month_plan
        if not plan:
            return
        
        # Plan notes
        plan_notes = plan.get('plan_notes', '') or bba.plan_notes
        if plan_notes:
            doc.add_heading("Notes on the 12-Month Recommendations Plan", level=2)
            doc.add_paragraph(plan_notes)
            doc.add_paragraph()
        
        # Recommendations
        recommendations = plan.get('recommendations', [])
        
        for rec in recommendations:
            # Recommendation heading
            number = rec.get('number', '')
            title = rec.get('title', '')
            timing = rec.get('timing', '')
            doc.add_heading(f"Recommendation {number}: {title}", level=2)
            
            # Timing
            if timing:
                para = doc.add_paragraph()
                run = para.add_run(f"Timing: {timing}")
                run.italic = True
            
            # Purpose
            purpose = rec.get('purpose', '')
            if purpose:
                doc.add_heading("Purpose", level=3)
                doc.add_paragraph(purpose)
            
            # Key Objectives
            objectives = rec.get('key_objectives', [])
            if objectives:
                doc.add_heading("Key Objectives", level=3)
                for obj in objectives:
                    doc.add_paragraph(obj, style='List Bullet')
            
            # Actions to Complete
            actions = rec.get('actions', [])
            if actions:
                doc.add_heading("Actions to Complete", level=3)
                for i, action in enumerate(actions, 1):
                    doc.add_paragraph(f"{i}. {action}")
            
            # BBA Support Outline
            bba_support = rec.get('bba_support', '')
            if bba_support:
                doc.add_heading("BBA Support Outline", level=3)
                doc.add_paragraph(bba_support)
            
            # Expected Outcomes
            outcomes = rec.get('expected_outcomes', [])
            if outcomes:
                doc.add_heading("Expected Outcomes", level=3)
                for outcome in outcomes:
                    doc.add_paragraph(outcome, style='List Bullet')
            
            doc.add_paragraph()  # Spacing between recommendations
        
        # Timeline Summary
        timeline = plan.get('timeline_summary', {})
        if timeline and timeline.get('rows'):
            self._add_page_break(doc)
            doc.add_heading("Implementation Timeline", level=2)
            
            rows_data = timeline.get('rows', [])
            
            # Create table
            table = doc.add_table(rows=1, cols=5)
            table.style = 'Table Grid'
            
            # Header row
            header_cells = table.rows[0].cells
            headers = ['Rec #', 'Recommendation', 'Focus Area', 'Timing', 'Key Outcome']
            for i, header in enumerate(headers):
                header_cells[i].text = header
                header_cells[i].paragraphs[0].runs[0].bold = True
            
            # Data rows
            for row_data in rows_data:
                row = table.add_row()
                row.cells[0].text = str(row_data.get('rec_number', ''))
                row.cells[1].text = row_data.get('recommendation', '')
                row.cells[2].text = row_data.get('focus_area', '')
                row.cells[3].text = row_data.get('timing', '')
                row.cells[4].text = row_data.get('key_outcome', '')
    
    def _add_footer(self, doc: Document, bba: BBA):
        """Add footer to document."""
        client_name = bba.client_name or "Client"
        version = bba.report_version or 1
        date_str = datetime.utcnow().strftime("%B %Y")
        
        # Add a section for footer
        section = doc.sections[0]
        footer = section.footer
        footer_para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer_para.add_run(
            f"Confidential – Prepared by Benchmark Business Advisory for {client_name} | "
            f"Version {version}.0 – {date_str}"
        )
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(128, 128, 128)


# Factory function
def get_bba_report_exporter() -> BBAReportExporter:
    """Get a BBA report exporter instance."""
    return BBAReportExporter()
