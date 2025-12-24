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
        # Roadmap can be in ai_analysis or scoring_data - check both
        roadmap = ai_analysis.get("roadmap", []) or scoring_data.get("roadmap", [])
        scored_rows = scoring_data.get("scored_rows", [])
        
        # Get module_scores for fallback/merging
        module_scores = getattr(diagnostic, "module_scores", {}) or {}
        ranked_modules = module_scores.get("ranked", [])
        
        # If roadmap is empty or incomplete, build/merge with ranked_modules
        if not roadmap and ranked_modules:
            # Convert ranked_modules to roadmap format
            roadmap = []
            for module in ranked_modules:
                roadmap_item = {
                    "module": module.get("module", ""),
                    "name": module.get("module_name", module.get("module", "")),
                    "score": module.get("score", 0.0),
                    "rank": module.get("rank", 0),
                    "rag": module.get("rag", "Amber"),
                    "whyPriority": module.get("whyPriority", f"Module {module.get('module', '')} requires attention based on score."),
                    "quickWins": module.get("quickWins", "Review and address module-specific gaps.")
                }
                roadmap.append(roadmap_item)
        elif roadmap and ranked_modules:
            # Merge: Use ranked_modules for accurate scores/ranks, but keep AI's whyPriority/quickWins
            roadmap_by_module = {item.get("module"): item for item in roadmap}
            merged_roadmap = []
            for module in ranked_modules:
                module_code = module.get("module", "")
                ai_item = roadmap_by_module.get(module_code, {})
                merged_item = {
                    "module": module_code,
                    "name": ai_item.get("name") or module.get("module_name", module_code),
                    "score": module.get("score", 0.0),  # Use calculated score
                    "rank": module.get("rank", 0),  # Use calculated rank
                    "rag": module.get("rag", "Amber"),  # Use calculated RAG
                    "whyPriority": ai_item.get("whyPriority", module.get("whyPriority", f"Module {module_code} requires attention.")),
                    "quickWins": ai_item.get("quickWins", module.get("quickWins", "Review and address module-specific gaps."))
                }
                merged_roadmap.append(merged_item)
            roadmap = merged_roadmap
        
        # Format dates
        created_date = diagnostic.created_at.strftime("%B %d, %Y") if diagnostic.created_at else ""
        completed_date = diagnostic.completed_at.strftime("%B %d, %Y") if diagnostic.completed_at else ""
        
        # Get user name
        user_name = user.name or user.email or "Unknown User"
        
        # Get business / company name from engagement if available
        business_name = ""
        try:
            engagement = getattr(diagnostic, "engagement", None)
            if engagement is not None:
                business_name = (
                    getattr(engagement, "business_name", None)
                    or getattr(engagement, "engagement_name", None)
                    or ""
                )
        except Exception:
            business_name = ""
        
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
    {ReportService._build_advice_section(advice, roadmap)}
    {ReportService._build_advisor_report_section(advisor_report, business_name)}
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
    def _build_advice_section(advice: str, roadmap: List[Dict[str, Any]]) -> str:
        """
        Build Diagnostic Advice section.
        
        This section should ONLY contain the roadmap table.
        NO narrative advice content - that goes in the Advisor Report section.
        """
        if not roadmap:
            return ""
        
        return f"""
    <div class="page-break"></div>
    <div class="section">
        <h2>Diagnostic Advice</h2>
        {ReportService._build_diagnostic_advice_table(roadmap)}
    </div>"""
    
    @staticmethod
    def _build_advisor_report_section(advisor_report: str, business_name: str = "") -> str:
        """Build advisor report section (detailed narrative paragraphs, not tables)."""
        if not advisor_report:
            return ""
        
        # The advisor report is generated as HTML/Markdown containing numbered sections
        # (1. Executive Summary, 2. Module Findings, 3. Task List by Module, 4. Additional Bespoke Tasks).
        # We add the major heading "Sale-Ready Assessment Report for [Company]" above it.
        advisor_html = ReportService._markdown_to_html(advisor_report)
        
        # Build major heading text
        company_text = business_name.strip() if business_name else "the business"
        heading_html = f"<h1>Sale-Ready Assessment Report for {ReportService._escape_html(company_text)}</h1>"
        
        return f"""
    <div class="page-break"></div>
    <div class="section advisor-report-section">
        {heading_html}
        <div class="advisor-report">{advisor_html}</div>
    </div>"""
    
    @staticmethod
    def _build_scoring_section(
        scored_rows: List[Dict[str, Any]],
        client_summary: str,
        roadmap: List[Dict[str, Any]] = None
    ) -> str:
        """
        Build scoring section with:
        - Scored Responses table
        - Client Summary (narrative + Roadmap table)
        """
        sections: List[str] = []
        
        # Scored Responses Table
        if scored_rows:
            sections.append(ReportService._build_scored_responses_table(scored_rows))
        
        # Client Summary section (narrative + roadmap table)
        if client_summary or roadmap:
            client_summary_html = ""
            if client_summary:
                client_summary_html = ReportService._markdown_to_html(client_summary)
            
            roadmap_table_html = ""
            if roadmap:
                roadmap_table_html = ReportService._build_roadmap_table(roadmap)
            
            sections.append(f"""
    <div class="section">
        <h2>Client Summary</h2>
        {f'<div class="client-summary">{client_summary_html}</div>' if client_summary_html else ''}
        {roadmap_table_html}
    </div>""")
        
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
        for row in scored_rows:
            question = ReportService._escape_html(str(row.get("question", "")))
            response = ReportService._escape_html(str(row.get("response", "")))
            score = str(row.get("score", ""))
            module = str(row.get("module", ""))
            
            rows_html += f"""
            <tr>
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
                    <th style="width:50%;">Question</th>
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
        """
        Build roadmap table for Client Summary section.
        
        Columns: Module | RAG | Score | Rank | Why Priority | Quick Wins
        Same format as diagnostic advice table but different column order.
        """
        if not roadmap:
            return ""
        
        rows_html = ""
        for item in roadmap:
            if not isinstance(item, dict):
                continue
            
            # Get module name (prefer full name, fall back to code)
            module_name = item.get("name") or item.get("module", "")
            if not module_name:
                continue
            
            module_name = ReportService._escape_html(str(module_name))
            rag = ReportService._escape_html(str(item.get("rag", "")))
            score = str(item.get("score", ""))
            rank = str(item.get("rank", ""))
            why_priority = ReportService._escape_html(str(item.get("whyPriority", "")))
            quick_wins = ReportService._escape_html(str(item.get("quickWins", "")))
            
            rows_html += f"""
            <tr>
                <td>{module_name}</td>
                <td>{rag}</td>
                <td>{score}</td>
                <td>{rank}</td>
                <td>{why_priority}</td>
                <td>{quick_wins}</td>
            </tr>"""
        
        if not rows_html:
            return ""
        
        return f"""
        <h3>Roadmap</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width:24%;">Module</th>
                    <th style="width:10%;">RAG</th>
                    <th style="width:10%;">Score</th>
                    <th style="width:8%;">Rank</th>
                    <th style="width:24%;">Why Priority</th>
                    <th style="width:24%;">Quick Wins</th>
                </tr>
            </thead>
            <tbody>{rows_html}
            </tbody>
        </table>"""
    
    @staticmethod
    def _build_diagnostic_advice_table(roadmap: List[Dict[str, Any]]) -> str:
        """
        Build the Diagnostic Advice table using roadmap data.
        
        Columns:
        - Rank
        - Sale-Ready Module
        - RAG
        - Score
        - Why Priority
        - Quick Wins
        """
        if not roadmap:
            return "<p>No roadmap data available.</p>"
        
        rows_html = ""
        for item in roadmap:
            if not isinstance(item, dict):
                continue
                
            rank = str(item.get("rank", ""))
            # Prefer full module name if available, else fall back to code
            module_name = item.get("name") or item.get("module", "")
            if not module_name:
                continue  # Skip items without module info
            module_name = ReportService._escape_html(str(module_name))
            rag = ReportService._escape_html(str(item.get("rag", "")))
            score = str(item.get("score", ""))
            why_priority = ReportService._escape_html(str(item.get("whyPriority", "")))
            quick_wins = ReportService._escape_html(str(item.get("quickWins", "")))
            
            rows_html += f"""
            <tr>
                <td>{rank}</td>
                <td>{module_name}</td>
                <td>{rag}</td>
                <td>{score}</td>
                <td>{why_priority}</td>
                <td>{quick_wins}</td>
            </tr>"""
        
        if not rows_html:
            return "<p>No valid roadmap data available.</p>"
        
        return f"""
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width:8%;">Rank</th>
                    <th style="width:24%;">Sale-Ready Module</th>
                    <th style="width:10%;">RAG</th>
                    <th style="width:10%;">Score</th>
                    <th style="width:24%;">Why Priority</th>
                    <th style="width:24%;">Quick Wins</th>
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
            font-size: 16px;
            line-height: 1.7;
            color: #333;
        }
        
        /* Headings */
        h1 {
            font-size: 28px;
            font-weight: bold;
            margin-top: 20px;
            margin-bottom: 18px;
            color: #1a1a1a;
        }
        
        h2 {
            font-size: 22px;
            font-weight: bold;
            margin-top: 26px;
            margin-bottom: 14px;
            color: #2a2a2a;
        }
        
        h3 {
            font-size: 18px;
            font-weight: bold;
            margin-top: 22px;
            margin-bottom: 12px;
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
        
        .summary, .advice, .client-summary, .advisor-report {
            margin-top: 10px;
            padding: 10px;
        }
        
        .advisor-report-section {
            margin-top: 20px;
        }
        
        /* Ensure advisor report paragraphs are displayed properly */
        .advisor-report p {
            margin: 10px 0;
            line-height: 1.6;
        }
        
        .advisor-report h2 {
            margin-top: 20px;
            margin-bottom: 10px;
            font-size: 18px;
            font-weight: bold;
        }
        
        .advisor-report h3 {
            margin-top: 15px;
            margin-bottom: 8px;
            font-size: 16px;
            font-weight: bold;
        }
        
        /* Ensure tables in advisor report are styled but paragraphs are primary */
        .advisor-report table {
            margin: 15px 0;
            width: 100%;
            border-collapse: collapse;
        }
        
        .advisor-report table th,
        .advisor-report table td {
            border: 1px solid #444;
            padding: 8px;
            text-align: left;
        }
        
        .advisor-report table th {
            background-color: #f0f0f0;
            font-weight: bold;
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
            padding: 10px;
            text-align: left;
            font-size: 15px;
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

