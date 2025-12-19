"""
PDF Report Generation Service for Diagnostics
"""
import markdown
from datetime import datetime
from typing import Dict, Any, Optional, List
from io import BytesIO
from xhtml2pdf import pisa
import logging

logger = logging.getLogger(__name__)


class ReportService:
    """Service for generating PDF reports from diagnostic data."""
    
    @staticmethod
    def generate_pdf_report(
        diagnostic: Any,
        user: Any,
        question_text_map: Dict[str, str]
    ) -> bytes:
        """
        Generate PDF report for a diagnostic.
        
        Args:
            diagnostic: Diagnostic model instance
            user: User model instance (report owner)
            question_text_map: Mapping of question keys to question text
            
        Returns:
            PDF bytes
        """
        # Build HTML content
        html_content = ReportService._build_html_report(
            diagnostic=diagnostic,
            user=user,
            question_text_map=question_text_map
        )
        
        # Generate PDF from HTML
        pdf_bytes = ReportService._html_to_pdf(html_content)
        
        return pdf_bytes
    
    @staticmethod
    def _build_html_report(
        diagnostic: Any,
        user: Any,
        question_text_map: Dict[str, str]
    ) -> str:
        """Build HTML report content."""
        
        # Extract data from diagnostic
        ai_analysis = diagnostic.ai_analysis or {}
        scoring_data = diagnostic.scoring_data or {}
        user_responses = diagnostic.user_responses or {}
        
        # Get summary, advice, roadmap, etc.
        # These fields are generated as Markdown by the LLM, so we convert them to HTML.
        summary = ai_analysis.get("summary", "")
        advice = ai_analysis.get("advice", "")
        advisor_report = ai_analysis.get("advisorReport", "")
        client_summary = ai_analysis.get("clientSummary", "")
        roadmap = ai_analysis.get("roadmap", [])
        scored_rows = scoring_data.get("scored_rows", [])
        
        # Format dates
        created_date = diagnostic.created_at.strftime("%B %d, %Y") if diagnostic.created_at else ""
        completed_date = diagnostic.completed_at.strftime("%B %d, %Y") if diagnostic.completed_at else ""
        
        # Get user name
        user_name = user.name or user.email or "Unknown User"
        
        # Build Q&A data (all responses with question text)
        qa_data = ReportService._build_qa_data(user_responses, question_text_map)
        
        # Generate HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TrinityAi Diagnostic Report</title>
    <style>
        {ReportService._get_css_styles()}
    </style>
</head>
<body>
    {ReportService._build_header_section(user_name, created_date, completed_date)}
    {ReportService._build_summary_section(summary)}
    {ReportService._build_advice_section(advice)}
    {ReportService._build_advisor_report_section(advisor_report)}
    {ReportService._build_scoring_section(scored_rows, client_summary, roadmap)}
    {ReportService._build_all_responses_section(qa_data)}
</body>
</html>"""
        
        return html
    
    @staticmethod
    def _build_header_section(user_name: str, created_date: str, completed_date: str) -> str:
        """Build header section."""
        date_display = completed_date if completed_date else created_date
        return f"""
    <div class="header-section">
        <h1>TrinityAi Diagnostic</h1>
        <p><strong>User:</strong> {ReportService._escape_html(user_name)}</p>
        <p><strong>Date:</strong> {date_display}</p>
    </div>"""
    
    @staticmethod
    def _build_summary_section(summary: str) -> str:
        """Build diagnostic summary section."""
        if not summary:
            return ""
        
        # Convert Markdown to HTML (headings, bullets, tables, etc.)
        summary_html = ReportService._markdown_to_html(summary)
        
        return f"""
    <div class="section">
        <h2>Diagnostic Summary</h2>
        <div class="summary">{summary_html}</div>
    </div>"""
    
    @staticmethod
    def _build_advice_section(advice: str) -> str:
        """Build diagnostic advice section."""
        if not advice:
            return ""
        
        advice_html = ReportService._markdown_to_html(advice)
        
        return f"""
    <div class="page-break"></div>
    <div class="section">
        <h2>Diagnostic Advice</h2>
        <div class="advice">{advice_html}</div>
    </div>"""
    
    @staticmethod
    def _build_advisor_report_section(advisor_report: str) -> str:
        """Build advisor report section (detailed narrative and tables)."""
        if not advisor_report:
            return ""
        
        advisor_html = ReportService._markdown_to_html(advisor_report)
        
        return f"""
    <div class="page-break"></div>
    <div class="section">
        <h2>Advisor Report</h2>
        <div class="advisor-report">{advisor_html}</div>
    </div>"""
    
    @staticmethod
    def _build_scoring_section(
        scored_rows: List[Dict[str, Any]],
        client_summary: str,
        roadmap: List[Dict[str, Any]]
    ) -> str:
        """Build scoring section with tables (scored responses, client summary, roadmap)."""
        sections = []
        
        # Scored Responses Table
        if scored_rows:
            sections.append(ReportService._build_scored_responses_table(scored_rows))
        
        # Client Summary
        if client_summary:
            client_summary_html = ReportService._markdown_to_html(client_summary)
            sections.append(f"""
    <div class="section">
        <h2>Client Summary</h2>
        <div class="client-summary">{client_summary_html}</div>
    </div>""")
        
        # Roadmap Table
        if roadmap:
            sections.append(ReportService._build_roadmap_table(roadmap))
        
        if sections:
            return f"""
    <div class="page-break"></div>
    <div class="section">
        <h2>Scoring</h2>
        {''.join(sections)}
    </div>"""
        
        return ""
    
    @staticmethod
    def _build_scored_responses_table(scored_rows: List[Dict[str, Any]]) -> str:
        """Build scored responses table."""
        rows_html = ""
        for idx, row in enumerate(scored_rows, 1):
            question = ReportService._escape_html(str(row.get("question", "")))
            response = ReportService._escape_html(str(row.get("response", "")))
            score = str(row.get("score", ""))
            module = str(row.get("module", ""))
            
            rows_html += f"""
            <tr>
                <td>{idx}</td>
                <td>{question}</td>
                <td>{response}</td>
                <td>{score}</td>
                <td>{module}</td>
            </tr>"""
        
        return f"""
        <h3>Scored Responses</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width:5%;">#</th>
                    <th style="width:45%;">Question</th>
                    <th style="width:20%;">Response</th>
                    <th style="width:10%;">Score</th>
                    <th style="width:20%;">Module</th>
                </tr>
            </thead>
            <tbody>{rows_html}
            </tbody>
        </table>"""
    
    @staticmethod
    def _build_roadmap_table(roadmap: List[Dict[str, Any]]) -> str:
        """Build roadmap table."""
        rows_html = ""
        for item in roadmap:
            module = ReportService._escape_html(str(item.get("module", "")))
            rag = ReportService._escape_html(str(item.get("rag", "")))
            score = str(item.get("score", ""))
            rank = str(item.get("rank", ""))
            why_priority = ReportService._escape_html(str(item.get("whyPriority", "")))
            quick_wins = ReportService._escape_html(str(item.get("quickWins", "")))
            
            rows_html += f"""
            <tr>
                <td>{module}</td>
                <td>{rag}</td>
                <td>{score}</td>
                <td>{rank}</td>
                <td>{why_priority}</td>
                <td>{quick_wins}</td>
            </tr>"""
        
        return f"""
        <h3>Roadmap</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Module</th>
                    <th>RAG</th>
                    <th>Score</th>
                    <th>Rank</th>
                    <th>Why Priority</th>
                    <th>Quick Wins</th>
                </tr>
            </thead>
            <tbody>{rows_html}
            </tbody>
        </table>"""
    
    @staticmethod
    def _build_all_responses_section(qa_data: List[Dict[str, str]]) -> str:
        """Build all responses section."""
        rows_html = ""
        for idx, qa in enumerate(qa_data, 1):
            question = ReportService._escape_html(qa.get("question", ""))
            answer_html = ReportService._format_answer(qa.get("answer"))
            
            rows_html += f"""
            <tr>
                <td>{idx}</td>
                <td>{question}</td>
                <td>{answer_html}</td>
            </tr>"""
        
        return f"""
    <div class="page-break"></div>
    <div class="section">
        <h3>All Responses</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width:5%;">#</th>
                    <th style="width:45%;">Question</th>
                    <th style="width:50%;">Response</th>
                </tr>
            </thead>
            <tbody>{rows_html}
            </tbody>
        </table>
    </div>"""
    
    @staticmethod
    def _build_qa_data(
        user_responses: Dict[str, Any],
        question_text_map: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """Build Q&A data with question text mapping."""
        qa_data = []
        
        if not user_responses:
            return qa_data
        
        for key, value in user_responses.items():
            # Skip None values
            if value is None:
                continue
                
            question_text = question_text_map.get(key, key)
            qa_data.append({
                "question": question_text,
                "answer": value
            })
        
        return qa_data
    
    @staticmethod
    def _format_answer(answer: Any) -> str:
        """Format answer based on type (text, array, dict, etc.)."""
        if answer is None:
            return ""
        
        if isinstance(answer, str):
            return ReportService._escape_html(answer)
        
        if isinstance(answer, (list, tuple)):
            # Array - bullet list
            items = [f"<li>{ReportService._escape_html(str(item))}</li>" for item in answer]
            return f"<ul>{''.join(items)}</ul>"
        
        if isinstance(answer, dict):
            # Associative array - key-value list
            items = [
                f"<li><strong>{ReportService._escape_html(str(k))}:</strong> {ReportService._escape_html(str(v))}</li>"
                for k, v in answer.items()
            ]
            return f"<ul>{''.join(items)}</ul>"
        
        # Default: convert to string
        return ReportService._escape_html(str(answer))
    
    @staticmethod
    def _markdown_to_html(text: str) -> str:
        """Convert Markdown text (with tables, lists, headings) to HTML."""
        if not text:
            return ""
        
        # Use extensions that support tables and better list handling
        return markdown.markdown(
            text,
            extensions=[
                "extra",        # tables, definition lists, etc.
                "sane_lists",   # better list handling
                "nl2br",        # preserve line breaks
                "fenced_code",
            ],
        )
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        if not isinstance(text, str):
            text = str(text)
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;"))
    
    @staticmethod
    def _get_css_styles() -> str:
        """Get CSS styles for PDF."""
        return """
        @page {
            size: A4;
            margin: 25mm 20mm 25mm 20mm;
        }
        
        /* Base Typography */
        body, td, li, p {
            font-family: DejaVu Sans, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            color: #333;
        }
        
        /* Headings */
        h1 {
            font-size: 24px;
            font-weight: bold;
            margin-top: 20px;
            margin-bottom: 15px;
            color: #1a1a1a;
        }
        
        h2 {
            font-size: 20px;
            font-weight: bold;
            margin-top: 25px;
            margin-bottom: 12px;
            color: #2a2a2a;
        }
        
        h3 {
            font-size: 16px;
            font-weight: bold;
            margin-top: 20px;
            margin-bottom: 10px;
            color: #3a3a3a;
        }
        
        /* Sections */
        .header-section {
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #444;
        }
        
        .section {
            margin-bottom: 30px;
        }
        
        .summary, .advice, .client-summary {
            margin-top: 10px;
            padding: 10px;
        }
        
        /* Tables */
        table.data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            margin-bottom: 20px;
        }
        
        table.data-table th,
        table.data-table td {
            border: 1px solid #444;
            padding: 8px;
            text-align: left;
        }
        
        table.data-table th {
            background-color: #f0f0f0;
            font-weight: bold;
        }
        
        table.data-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        /* Lists */
        ul, ol {
            margin: 10px 0;
            padding-left: 30px;
        }
        
        li {
            margin: 5px 0;
        }
        
        /* Page Breaks */
        .page-break {
            page-break-after: always;
        }
        
        /* Sub-tables (nested) */
        .sub-table {
            font-size: 10px;
        }
        
        .sub-table th,
        .sub-table td {
            padding: 4px;
        }
        """
    
    @staticmethod
    def _html_to_pdf(html_content: str) -> bytes:
        """Convert HTML to PDF bytes using xhtml2pdf."""
        try:
            result = BytesIO()
            pdf = pisa.pisaDocument(BytesIO(html_content.encode("utf-8")), result)
            
            if pdf.err:
                error_msg = f"PDF generation error: {pdf.err}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            return result.getvalue()
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            raise Exception(f"Failed to generate PDF: {str(e)}")
    
    @staticmethod
    def get_download_filename(diagnostic: Any, user: Any) -> str:
        """
        Generate download filename for diagnostic report.
        
        Format: YYYY-MM-DD_HH-MM-SS-TrinityAi-diagnostic-LastName_FirstName.pdf
        """
        # Get date (use completed_at if available, else created_at)
        date_obj = diagnostic.completed_at or diagnostic.created_at
        if date_obj:
            file_date = date_obj.strftime("%Y-%m-%d_%H-%M-%S")
        else:
            file_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Get user name parts
        name = user.name or user.email or "Unknown"
        name_parts = name.split()
        
        if len(name_parts) >= 2:
            last_name = name_parts[-1]
            first_name = name_parts[0]
        else:
            last_name = name_parts[0] if name_parts else "User"
            first_name = ""
        
        # Clean names (remove special characters)
        last_name = "".join(c for c in last_name if c.isalnum() or c in ('-', '_'))
        first_name = "".join(c for c in first_name if c.isalnum() or c in ('-', '_'))
        
        if first_name:
            filename = f"{file_date}-TrinityAi-diagnostic-{last_name}_{first_name}.pdf"
        else:
            filename = f"{file_date}-TrinityAi-diagnostic-{last_name}.pdf"
        
        return filename

