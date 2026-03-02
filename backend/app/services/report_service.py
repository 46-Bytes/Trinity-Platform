"""
PDF Report Generation Service for Diagnostics
"""
import json
import re
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
        try:
            logger.info(
                "Starting PDF report generation for diagnostic_id=%s user_id=%s",
                getattr(diagnostic, "id", None),
                getattr(user, "id", None),
            )
        except Exception:
            logger.info("Starting PDF report generation (could not read diagnostic/user ids)")

        # Build HTML content
        html_content = ReportService._build_html_report(
            diagnostic=diagnostic,
            user=user,
            question_text_map=question_text_map
        )
        logger.debug("HTML report built; length=%s characters", len(html_content or ""))
        
        # Generate PDF from HTML
        pdf_bytes = ReportService._html_to_pdf(html_content)
        logger.info(
            "Finished PDF generation for diagnostic_id=%s (size=%s bytes)",
            getattr(diagnostic, "id", None),
            len(pdf_bytes or b""),
        )
        
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

        logger.debug(
            "ReportService _build_html_report: summary_len=%s advice_len=%s advisor_report_len=%s "
            "client_summary_len=%s roadmap_len=%s scored_rows_len=%s ranked_modules_len=%s",
            len(summary or ""),
            len(advice or ""),
            len(advisor_report or ""),
            len(client_summary or ""),
            len(roadmap or []),
            len(scored_rows or []),
            len(ranked_modules or []),
        )
        
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

        logger.debug(
            "ReportService _build_html_report: final roadmap_len=%s; example_item=%s",
            len(roadmap or []),
            (roadmap or [None])[0],
        )
        
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
        logger.debug(
            "ReportService _build_html_report: qa_data_len=%s (user_responses_keys=%s)",
            len(qa_data or []),
            list(user_responses.keys()) if isinstance(user_responses, dict) else "n/a",
        )
        
        # Generate HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TrinityAI Diagnostic Report</title>
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
        <h1>TrinityAI Diagnostic</h1>
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
        logger.debug(
            "ReportService _build_scoring_section: scored_rows_len=%s client_summary_len=%s roadmap_len=%s",
            len(scored_rows or []),
            len(client_summary or ""),
            len(roadmap or []) if roadmap is not None else 0,
        )
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
            question = ReportService._wrap_cell_text(ReportService._escape_html(str(row.get("question", ""))), 40)

            # Matrix/complex responses would stringify to a massive string
            # that overflows the fixed 20%-wide column → negative availWidth
            # in xhtml2pdf.  Summarise them instead.
            response_raw = row.get("response", "")
            if isinstance(response_raw, list):
                response = f"[{len(response_raw)} entries]"
            elif isinstance(response_raw, dict):
                response = "[Complex response]"
            else:
                response = ReportService._wrap_cell_text(ReportService._escape_html(str(response_raw)), 15)

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
        <table class="data-table" style="border-collapse: collapse; width: 100%; table-layout: fixed;">
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
            logger.debug("ReportService _build_roadmap_table: empty roadmap list")
            return ""
        
        rows_html = ""
        for item in roadmap:
            if not isinstance(item, dict):
                continue
            
            # Get module name (prefer full name, fall back to code)
            module_name = item.get("name") or item.get("module", "")
            if not module_name:
                continue
            
            module_name = ReportService._wrap_cell_text(ReportService._escape_html(str(module_name)), 18)
            rag = ReportService._escape_html(str(item.get("rag", "")))
            score = str(item.get("score", ""))
            rank = str(item.get("rank", ""))
            why_priority = ReportService._wrap_cell_text(ReportService._escape_html(str(item.get("whyPriority", ""))), 18)
            quick_wins = ReportService._wrap_cell_text(ReportService._escape_html(str(item.get("quickWins", ""))), 18)

            rows_html += f"""
            <tr>
                <td style="text-align: left;">{module_name}</td>
                <td style="text-align: center;">{rag}</td>
                <td style="text-align: center;">{score}</td>
                <td style="text-align: center;">{rank}</td>
                <td style="text-align: left;">{why_priority}</td>
                <td style="text-align: left;">{quick_wins}</td>
            </tr>"""
        
        if not rows_html:
            logger.warning(
                "ReportService _build_roadmap_table: no valid rows generated from roadmap=%s",
                roadmap,
            )
            return ""
        
        return f"""
        <h3>Roadmap</h3>
        <table class="data-table" style="border-collapse: collapse; width: 100%; table-layout: fixed;">
            <thead>
                <tr>
                    <th style="width:22%; text-align: left;">Module</th>
                    <th style="width:10%; text-align: center;">RAG</th>
                    <th style="width:10%; text-align: center;">Score</th>
                    <th style="width:10%; text-align: center;">Rank</th>
                    <th style="width:24%; text-align: left;">Why Priority</th>
                    <th style="width:24%; text-align: left;">Quick Wins</th>
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
            module_name = ReportService._wrap_cell_text(ReportService._escape_html(str(module_name)), 18)
            rag = ReportService._escape_html(str(item.get("rag", "")))
            score = str(item.get("score", ""))
            why_priority = ReportService._wrap_cell_text(ReportService._escape_html(str(item.get("whyPriority", ""))), 18)
            quick_wins = ReportService._wrap_cell_text(ReportService._escape_html(str(item.get("quickWins", ""))), 18)

            rows_html += f"""
            <tr>
                <td style="text-align: center;">{rank}</td>
                <td style="text-align: left;">{module_name}</td>
                <td style="text-align: center;">{rag}</td>
                <td style="text-align: center;">{score}</td>
                <td style="text-align: left;">{why_priority}</td>
                <td style="text-align: left;">{quick_wins}</td>
            </tr>"""
        
        if not rows_html:
            return "<p>No valid roadmap data available.</p>"
        
        return f"""
        <table class="data-table" style="border-collapse: collapse; width: 100%; table-layout: fixed;">
            <thead>
                <tr>
                    <th style="width:10%; text-align: center;">Rank</th>
                    <th style="width:22%; text-align: left;">Sale-Ready Module</th>
                    <th style="width:10%; text-align: center;">RAG</th>
                    <th style="width:10%; text-align: center;">Score</th>
                    <th style="width:24%; text-align: left;">Why Priority</th>
                    <th style="width:24%; text-align: left;">Quick Wins</th>
                </tr>
            </thead>
            <tbody>{rows_html}
            </tbody>
        </table>"""
    
    @staticmethod
    def _build_all_responses_section(qa_data: List[Dict[str, str]]) -> str:
        """Build all responses section.

        Uses class="data-table" (table-layout:fixed) — the same proven
        approach used by Scored Responses, Roadmap, and Diagnostic Advice.
        All cell content is plain text + <br/> only (no <ul>/<li>)
        via _format_answer_plain(), which prevents xhtml2pdf from
        miscalculating column widths.
        """
        logger.debug(
            "ReportService _build_all_responses_section: qa_data_len=%s", len(qa_data or [])
        )

        file_indicators = [
            'media_id', 'Media Id', 'mediaId',
            'file_name', 'File Name', 'fileName', 'filename',
            'file_type', 'File Type', 'fileType',
            'openai_file_id', 'Openai File Id', 'openaiFileId',
            'relative_path', 'Relative Path', 'relativePath',
        ]

        rows_html = ""

        for idx, qa in enumerate(qa_data, 1):
            question = ReportService._escape_html(qa.get("question", ""))
            answer = qa.get("answer")

            # File-upload detection (list-of-dicts with file indicator keys)
            is_matrix = (
                isinstance(answer, list)
                and len(answer) > 0
                and isinstance(answer[0], dict)
            )

            if is_matrix:
                is_file_data = any(
                    isinstance(row, dict) and any(ind in row for ind in file_indicators)
                    for row in answer
                )
                if is_file_data:
                    file_names = []
                    for row in answer:
                        if isinstance(row, dict):
                            file_name = (
                                row.get('file_name') or row.get('File Name') or
                                row.get('fileName') or row.get('filename') or
                                row.get('Filename') or ''
                            )
                            if file_name:
                                file_names.append(file_name)
                    answer_html = (
                        ', '.join(ReportService._wrap_cell_text(ReportService._escape_html(fn)) for fn in file_names)
                        if file_names else "Files uploaded"
                    )
                    # File uploads: normal 3-column row
                    rows_html += f"""
            <tr>
                <td style="text-align: center; width: 8%;">{idx}</td>
                <td style="width: 42%; word-wrap: break-word; overflow: hidden;">{question}</td>
                <td style="width: 50%; word-wrap: break-word; overflow: hidden;">{answer_html}</td>
            </tr>"""
                else:
                    # Matrix data — question header row + full-width sub-table row
                    matrix_html = ReportService._format_matrix_as_table(answer)
                    rows_html += f"""
            <tr>
                <td style="text-align: center; width: 8%;">{idx}</td>
                <td colspan="2" style="width: 92%; font-weight: bold; word-wrap: break-word; overflow: hidden;">{question}</td>
            </tr>
            <tr>
                <td colspan="3" style="padding: 2px 4px; overflow: hidden;">{matrix_html}</td>
            </tr>"""
            else:
                # All other answers — plain text only (no <ul>)
                answer_html = ReportService._format_answer_plain(answer)

                # Ensure no empty cells — xhtml2pdf miscalculates widths on empty <td>
                if not answer_html:
                    answer_html = "&nbsp;"

                rows_html += f"""
            <tr>
                <td style="text-align: center; width: 8%;">{idx}</td>
                <td style="width: 42%; word-wrap: break-word; overflow: hidden;">{question}</td>
                <td style="width: 50%; word-wrap: break-word; overflow: hidden;">{answer_html}</td>
            </tr>"""

        return f"""
    <div class="page-break"></div>
    <div class="section">
        <h3>All Responses</h3>
        <table class="data-table" style="border-collapse: collapse; width: 100%; table-layout: fixed;">
            <thead>
                <tr>
                    <th style="width:8%; text-align: center;">#</th>
                    <th style="width:42%; text-align: left;">Question</th>
                    <th style="width:50%; text-align: left;">Response</th>
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
    def _humanize_label(slug: str) -> str:
        """Convert field_name to Field Name."""
        return slug.replace('_', ' ').replace('-', ' ').title()

    @staticmethod
    def _format_answer(answer: Any) -> str:
        """
        Format answer based on type (text, array, dict, etc.).
        
        Types:
        1. Matrix (list of dicts) - handled separately in _build_all_responses_section
        2. Associative array (dict) - bulleted list with key: value
        3. Simple array (list) - bulleted list
        4. Scalar (string/number) - direct value
        """
        if answer is None:
            return ""
        
        # Type 2: Associative array (dict)
        if isinstance(answer, dict):
            items = []
            for k, v in answer.items():
                key_label = ReportService._humanize_label(str(k))
                val_str = ReportService._escape_html(str(v))
                items.append(f"<li><strong>{ReportService._escape_html(key_label)}:</strong> {val_str}</li>")
            return f"<ul style=\"margin: 0; padding-left: 1.2em; list-style: disc;\">{''.join(items)}</ul>"
        
        # Type 3: Simple array (list)
        if isinstance(answer, (list, tuple)):
            items = []
            for item in answer:
                if isinstance(item, (dict, list)):
                    item_str = json.dumps(item)
                else:
                    item_str = str(item)
                items.append(f"<li>{ReportService._escape_html(item_str)}</li>")
            return f"<ul style=\"margin: 0; padding-left: 1.2em; list-style: disc;\">{''.join(items)}</ul>"
        
        # Type 4: Scalar (string/number)
        if isinstance(answer, str):
            return ReportService._escape_html(answer)
        
        # Default: convert to string
        return ReportService._escape_html(str(answer))
    
    @staticmethod
    def _format_answer_plain(answer: Any) -> str:
        """Format answer as flat text with <br/> separators only.

        Unlike _format_answer() this never emits block-level HTML
        (<ul>, <li>, <table>, etc.).  xhtml2pdf miscalculates column
        widths when block-level flowables sit inside table cells, so
        the All Responses table must use this method exclusively.
        """
        if answer is None:
            return ""

        # Matrix: list of dicts → one line per row
        if (isinstance(answer, list) and len(answer) > 0
                and isinstance(answer[0], dict)):
            lines: list[str] = []
            for i, row in enumerate(answer, 1):
                if not isinstance(row, dict):
                    continue
                pairs = ", ".join(
                    f"{ReportService._wrap_cell_text(ReportService._escape_html(ReportService._humanize_label(str(k))))}: "
                    f"{ReportService._wrap_cell_text(ReportService._escape_html(str(v)))}"
                    for k, v in row.items()
                    if v is not None and v != ""
                )
                if pairs:
                    lines.append(f"Row {i}: {pairs}")
            return "<br/>".join(lines) if lines else ""

        # Dict → key: value per line
        if isinstance(answer, dict):
            lines = []
            for k, v in answer.items():
                key_label = ReportService._wrap_cell_text(ReportService._escape_html(
                    ReportService._humanize_label(str(k))
                ))
                val_str = ReportService._wrap_cell_text(ReportService._escape_html(str(v)))
                lines.append(f"{key_label}: {val_str}")
            return "<br/>".join(lines)

        # Simple list/tuple → one item per line
        if isinstance(answer, (list, tuple)):
            items = []
            for item in answer:
                if isinstance(item, (dict, list)):
                    item_str = json.dumps(item)
                else:
                    item_str = str(item)
                items.append(ReportService._wrap_cell_text(ReportService._escape_html(item_str)))
            return "<br/>".join(items)

        # Scalar
        if isinstance(answer, str):
            return ReportService._wrap_cell_text(ReportService._escape_html(answer))

        return ReportService._wrap_cell_text(ReportService._escape_html(str(answer)))

    @staticmethod
    def _format_matrix_as_table(answer: List[Dict[str, Any]]) -> str:
        """Render a matrix response (list of dicts) as an HTML sub-table.

        Each dict key becomes a column header; each list item becomes a row.
        Uses the .sub-table CSS class with table-layout:auto so xhtml2pdf
        can size columns naturally within the parent cell.
        """
        if not answer:
            return ""

        # Collect all unique keys across rows to use as column headers,
        # preserving insertion order from the first row that has each key.
        seen_keys: dict[str, None] = {}
        for row in answer:
            if isinstance(row, dict):
                for k in row:
                    if k not in seen_keys:
                        seen_keys[k] = None
        columns = list(seen_keys.keys())

        if not columns:
            return ""

        # Calculate max chars per cell based on column count
        # A4 usable width ~170mm, minus cell padding/borders → ~70 usable chars at 10px font
        col_max = max(70 // len(columns), 8)

        # Build header row
        header_cells = "".join(
            f"<th>{ReportService._wrap_cell_text(ReportService._escape_html(ReportService._humanize_label(str(c))), col_max)}</th>"
            for c in columns
        )

        # Build data rows
        body_rows = ""
        for row in answer:
            if not isinstance(row, dict):
                continue
            cells = ""
            for c in columns:
                val = row.get(c, "")
                if val is None or val == "":
                    cells += "<td>&nbsp;</td>"
                elif isinstance(val, (dict, list)):
                    cells += f"<td>{ReportService._wrap_cell_text(ReportService._escape_html(json.dumps(val)), col_max)}</td>"
                else:
                    cells += f"<td>{ReportService._wrap_cell_text(ReportService._escape_html(str(val)), col_max)}</td>"
            body_rows += f"<tr>{cells}</tr>"

        return (
            f'<table class="sub-table" style="table-layout: fixed; width: 100%;">'
            f"<thead><tr>{header_cells}</tr></thead>"
            f"<tbody>{body_rows}</tbody>"
            f"</table>"
        )

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
    def _wrap_cell_text(text: str, max_line_len: int = 35) -> str:
        """Hard-wrap text for xhtml2pdf table cells.

        xhtml2pdf does not reliably honour word-wrap, overflow, or soft
        hyphens on table cells.  This method pre-wraps text in Python
        using <br/> tags so content never overflows the cell boundary.

        - Wraps at spaces when possible
        - Breaks long words with '-' and <br/>
        - Must be called AFTER _escape_html
        """
        if not text or len(text) <= max_line_len:
            return text
        words = text.split(' ')
        lines: list[str] = []
        current_line = ''
        for word in words:
            # If word fits on current line
            needed = len(current_line) + (1 if current_line else 0) + len(word)
            if needed <= max_line_len:
                current_line = (current_line + ' ' + word) if current_line else word
            else:
                # Flush current line
                if current_line:
                    lines.append(current_line)
                    current_line = ''
                # Break long words that exceed max_line_len
                while len(word) > max_line_len:
                    lines.append(word[:max_line_len - 1] + '-')
                    word = word[max_line_len - 1:]
                current_line = word
        if current_line:
            lines.append(current_line)
        return '<br/>'.join(lines)

    @staticmethod
    def _get_css_styles() -> str:
        """Get CSS styles for PDF."""
        return """
        @page {
            size: A4;
            margin: 25mm 20mm 25mm 20mm;
        }
        
        /* Base Typography - Arial font, black color */
        body, td, li, p {
            font-family: Arial, sans-serif;
            font-size: 16px;
            line-height: 1.4;
            color: #000000;
        }
        
        /* Headings - reduced spacing */
        h1 {
            font-size: 28px;
            font-weight: bold;
            margin-top: 10px;
            margin-bottom: 8px;
            color: #000000;
        }
        
        h2 {
            font-size: 22px;
            font-weight: bold;
            margin-top: 12px;
            margin-bottom: 6px;
            color: #000000;
        }
        
        h3 {
            font-size: 18px;
            font-weight: bold;
            margin-top: 10px;
            margin-bottom: 4px;
            color: #000000;
        }
        
        /* Sections - removed border, reduced spacing */
        .header-section {
            margin-bottom: 15px;
            padding-bottom: 10px;
        }
        
        .section {
            margin-bottom: 15px;
        }
        
        .summary, .advice, .client-summary, .advisor-report {
            margin-top: 5px;
            padding: 5px;
        }
        
        .advisor-report-section {
            margin-top: 10px;
        }
        
        /* Ensure advisor report paragraphs are displayed properly - reduced spacing */
        .advisor-report p {
            margin: 4px 0;
            line-height: 1.4;
            color: #000000;
        }
        
        .advisor-report h2 {
            margin-top: 10px;
            margin-bottom: 4px;
            font-size: 18px;
            font-weight: bold;
            color: #000000;
        }
        
        .advisor-report h3 {
            margin-top: 8px;
            margin-bottom: 3px;
            font-size: 16px;
            font-weight: bold;
            color: #000000;
        }
        
        /* Safe default for ALL tables (including markdown-generated ones).
           table-layout:auto lets xhtml2pdf size columns from content so
           narrow columns never go negative.  Our data-table class overrides
           this to fixed where we control the column widths. */
        table {
            table-layout: auto;
            border-collapse: collapse;
            width: 100%;
        }

        /* Ensure tables in advisor report are styled but paragraphs are primary */
        .advisor-report table {
            margin: 10px 0;
        }

        .advisor-report table th,
        .advisor-report table td {
            border: 1px solid #444;
            padding: 4px;
            text-align: left;
            color: #000000;
        }

        .advisor-report table th {
            background-color: #f0f0f0;
            font-weight: bold;
            color: #000000;
        }

        /* Explicit data tables — we control column widths so fixed is safe */
        table.data-table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            margin-top: 8px;
            margin-bottom: 10px;
        }

        table.data-table th,
        table.data-table td {
            border: 1px solid #444;
            padding: 4px 6px;
            text-align: left;
            font-size: 15px;
            color: #000000;
            vertical-align: top;
            word-wrap: break-word;
            overflow: hidden;
        }
        
        table.data-table th {
            background-color: #f0f0f0;
            font-weight: bold;
            color: #000000;
        }
        
        /* Center alignment for numeric/short columns */
        table.data-table th.center,
        table.data-table td.center {
            text-align: center;
        }
        
        table.data-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        /* Lists - reduced spacing between items */
        ul, ol {
            margin: 4px 0;
            padding-left: 30px;
        }
        
        li {
            margin: 2px 0;
            line-height: 1.4;
            color: #000000;
        }
        
        /* Page Breaks */
        .page-break {
            page-break-after: always;
        }
        
        /* Sub-tables (nested) */
        .sub-table {
            font-size: 10px;
            border-collapse: collapse;
            table-layout: fixed;
        }
        
        .sub-table th,
        .sub-table td {
            border: 1px solid #444;
            padding: 4px;
            text-align: left;
            color: #000000;
            word-wrap: break-word;
            overflow: hidden;
            vertical-align: top;
        }
        
        .sub-table th {
            background-color: #f0f0f0;
            font-weight: bold;
        }
        """
    
    @staticmethod
    def _strip_markdown_tables(html: str) -> str:
        """Replace markdown-generated <table> blocks (those without class=)
        with a plain-text fallback so xhtml2pdf doesn't crash on them."""

        def _table_to_text(match: re.Match) -> str:
            """Convert an HTML table to a simple line-per-row representation."""
            table_html = match.group(0)
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S)
            lines: list[str] = []
            for row_html in rows:
                cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)
                # Strip any remaining HTML tags inside cells
                clean = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
                lines.append(" | ".join(clean))
            text = "<br/>".join(lines)
            return f"<p>{text}</p>"

        # Only target tables that do NOT carry class= (i.e. markdown-generated)
        return re.sub(
            r"<table(?![^>]*\bclass=)[^>]*>.*?</table>",
            _table_to_text,
            html,
            flags=re.S,
        )

    @staticmethod
    def _html_to_pdf(html_content: str) -> bytes:
        """Convert HTML to PDF bytes using xhtml2pdf.

        If the first render attempt crashes (typically the negative-
        availWidth bug from a markdown-generated table with too many
        narrow columns), we strip those tables to plain text and retry.
        """
        try:
            logger.debug(
                "ReportService _html_to_pdf: starting PDF render; html_length=%s",
                len(html_content or ""),
            )
            result = BytesIO()
            pdf = pisa.pisaDocument(BytesIO(html_content.encode("utf-8")), result)

            if pdf.err:
                error_msg = f"PDF generation error: {pdf.err}"
                logger.error(error_msg)
                raise Exception(error_msg)

            return result.getvalue()

        except Exception as first_err:
            logger.warning(
                "ReportService _html_to_pdf: first render failed (%s), "
                "retrying with markdown tables stripped to plain text",
                first_err,
            )
            try:
                safe_html = ReportService._strip_markdown_tables(html_content)
                result2 = BytesIO()
                pdf2 = pisa.pisaDocument(
                    BytesIO(safe_html.encode("utf-8")), result2
                )
                if pdf2.err:
                    raise Exception(f"PDF generation error on retry: {pdf2.err}")
                logger.info(
                    "ReportService _html_to_pdf: retry succeeded after stripping tables"
                )
                return result2.getvalue()
            except Exception as retry_err:
                logger.error("Error generating PDF (retry also failed): %s", retry_err)
                raise Exception(f"Failed to generate PDF: {first_err}")
    
    @staticmethod
    def get_download_filename(diagnostic: Any, user: Any) -> str:
        """
        Generate download filename for diagnostic report.
        
        Format: YYYY-MM-DD_HH-MM-SS-TrinityAI-diagnostic-LastName_FirstName.pdf
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
            filename = f"{file_date}-TrinityAI-diagnostic-{last_name}_{first_name}.pdf"
        else:
            filename = f"{file_date}-TrinityAI-diagnostic-{last_name}.pdf"
        
        return filename