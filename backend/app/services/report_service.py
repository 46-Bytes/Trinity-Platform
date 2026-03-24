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
        question_text_map: Dict[str, str],
        structured_question_map: Optional[Dict[str, Any]] = None,
        advisor_name: str = ""
    ) -> bytes:
        """
        Generate PDF report for a diagnostic.

        Args:
            diagnostic: Diagnostic model instance
            user: User model instance (report owner)
            question_text_map: Mapping of question keys to question text
            structured_question_map: Mapping of question keys to field definitions
                for matrixdynamic/multipletext questions
            advisor_name: Name of the lead advisor for the cover page

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
            question_text_map=question_text_map,
            structured_question_map=structured_question_map,
            advisor_name=advisor_name
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
        question_text_map: Dict[str, str],
        structured_question_map: Optional[Dict[str, Any]] = None,
        advisor_name: str = ""
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
        
        # Get business / company name and firm name from engagement if available
        business_name = ""
        firm_name = ""
        try:
            engagement = getattr(diagnostic, "engagement", None)
            if engagement is not None:
                business_name = (
                    getattr(engagement, "business_name", None)
                    or getattr(engagement, "engagement_name", None)
                    or ""
                )
                firm = getattr(engagement, "firm", None)
                if firm is not None:
                    firm_name = getattr(firm, "firm_name", "") or ""
        except Exception:
            business_name = ""
            firm_name = ""

        # Determine diagnostic type for report title — prefer engagement.tool
        # (which holds "sale_ready" / "value_builder") over diagnostic.diagnostic_type
        # (which defaults to the generic "business_health_assessment").
        engagement_tool = getattr(engagement, "tool", None) if engagement is not None else None
        diagnostic_type = engagement_tool or getattr(diagnostic, "diagnostic_type", "") or "sale_ready"
        
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
    <div id="page-header">
        <p style="text-align: right; font-size: 10px; color: #c0c0c0; margin: 0; padding: 0;">Benchmark Business Advisory &nbsp;|&nbsp; {"Value Builder Diagnostic" if diagnostic_type == "value_builder" else "Sale Ready Diagnostic"} &nbsp;|&nbsp; Confidential</p>
    </div>
    {ReportService._build_cover_page(
        firm_name=firm_name,
        diagnostic_type=diagnostic_type,
        business_name=business_name,
        client_name=user_name,
        advisor_name=advisor_name,
        date_display=completed_date if completed_date else created_date
    )}
    {ReportService._build_advice_section(advice, roadmap)}
    {ReportService._build_advisor_report_section(advisor_report, business_name)}
    {ReportService._build_scoring_section(scored_rows, client_summary, roadmap, question_text_map=question_text_map, structured_question_map=structured_question_map)}
    {ReportService._build_all_responses_section(qa_data, structured_question_map=structured_question_map)}
</body>
</html>"""
        
        return html
    
    @staticmethod
    def _build_cover_page(
        firm_name: str,
        diagnostic_type: str,
        business_name: str,
        client_name: str,
        advisor_name: str,
        date_display: str
    ) -> str:
        """Build the cover/title page for the report."""
        # Map diagnostic type to display title
        type_titles = {
            "sale_ready": "Sale Ready Diagnostic Report",
            "value_builder": "Value Builder Diagnostic Report",
        }
        report_title = type_titles.get(diagnostic_type, "Diagnostic Report")

        # Map diagnostic type to short label for header
        type_labels = {
            "sale_ready": "Sale-Ready Assessment",
            "value_builder": "Value Builder Diagnostic",
            "business_health_assessment": "Business Health Assessment",
        }
        report_label = type_labels.get(diagnostic_type, "Diagnostic")

        # Build spaced-out firm name (e.g. "B E N C H M A R K")
        firm_display = firm_name.upper() if firm_name else ""
        firm_spaced = " &nbsp; ".join(firm_display) if firm_display else ""

        # Top-right header line removed per design request

        # Prepared for line
        prepared_for = f'<p class="cover-prepared-for">Prepared for: {ReportService._escape_html(client_name)}</p>' if client_name else ""

        # Advisor and date line
        meta_parts = []
        if advisor_name:
            meta_parts.append(f"Lead Advisor: {ReportService._escape_html(advisor_name)}")
        if date_display:
            meta_parts.append(f"Date: {date_display}")
        meta_line = f'<p class="cover-meta">{" &nbsp;|&nbsp; ".join(meta_parts)}</p>' if meta_parts else ""

        # Spaced CONFIDENTIAL - use plain spaces, rely on letter-spacing for spread
        confidential_spaced = "C O N F I D E N T I A L"

        return f"""
    <div class="cover-page">
        <p class="cover-firm-spaced">{firm_spaced if firm_spaced else ''}</p>
        <h1 class="cover-title">{ReportService._escape_html(report_title)}</h1>
        <hr class="cover-rule" />
        {f'<p class="cover-business-name">{ReportService._escape_html(business_name)}</p>' if business_name else ''}
        {prepared_for}
        {meta_line}
    </div>
    <div style="text-align: center; width: 100%;"><p style="text-align: center; font-size: 14px; font-weight: bold; color: #cc0000; margin-top: 30px;">{confidential_spaced}</p></div>"""

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
        
        # The advisor report is returned from Claude as raw HTML (the prompt
        # requests "a single HTML string").  Running it through the Markdown
        # converter would escape the existing HTML tags (e.g. <br/>, <table>)
        # turning them into visible literal text in the PDF.  We therefore
        # use the HTML as-is, only falling back to Markdown conversion when
        # the content looks like plain Markdown (no HTML tags present).
        if re.search(r"<(?:table|tr|td|th|br|h[1-6]|p|ul|ol|li|div|span)\b", advisor_report, re.IGNORECASE):
            advisor_html = advisor_report
        else:
            advisor_html = ReportService._markdown_to_html(advisor_report)
        # Strip Section 5 (Scoring Detail) — its "5a. Scored Responses" and
        # "5b. All Responses" tables are redundant with the dedicated formatted
        # sections and contain raw JSON values that render badly in the PDF.
        advisor_html = ReportService._strip_response_tables_from_summary(advisor_html)

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
        roadmap: List[Dict[str, Any]] = None,
        question_text_map: Optional[Dict[str, str]] = None,
        structured_question_map: Optional[Dict[str, Any]] = None
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
            sections.append(ReportService._build_scored_responses_table(
                scored_rows,
                question_text_map=question_text_map,
                structured_question_map=structured_question_map
            ))
        
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
    def _build_scored_responses_table(
        scored_rows: List[Dict[str, Any]],
        question_text_map: Optional[Dict[str, str]] = None,
        structured_question_map: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build scored responses table.

        Scored items (numeric score) → compact 4-column row.
        Informational items (score="Info" or complex response) → question
        header row + full-width formatted card block underneath.
        Structured questions (matrixdynamic/multipletext) use the survey
        definition for proper field labels.
        """
        # Build reverse lookup: question_text → question_key for structured matching
        reverse_text_map: Dict[str, str] = {}
        if question_text_map and structured_question_map:
            for qkey, qtext in question_text_map.items():
                if qkey in structured_question_map:
                    reverse_text_map[qtext] = qkey

        rows_html = ""
        for row in scored_rows:
            question_text = str(row.get("question", ""))
            question = ReportService._wrap_cell_text(
                ReportService._escape_html(question_text), 40
            )
            score = str(row.get("score", ""))
            module = str(row.get("module", ""))
            response = row.get("response", "")

            # Log complex responses for debugging
            logger.debug(
                "ScoredRow question=%r response_type=%s response_preview=%r score=%s",
                question_text[:60], type(response).__name__,
                str(response)[:120] if response else "", score,
            )

            # Check if this scored row corresponds to a structured question
            matched_key = reverse_text_map.get(question_text)
            # Also try matching by question_key if present in the row
            if not matched_key:
                row_key = row.get("question_key", "")
                if row_key and structured_question_map and row_key in structured_question_map:
                    matched_key = row_key

            if matched_key and structured_question_map:
                struct_info = structured_question_map[matched_key]
                response_html = ReportService._render_structured_response(
                    response, struct_info["fields"], struct_info["type"]
                )
                is_block = True
            else:
                # Runtime detection: parse response and check if it's complex data
                parsed_response = ReportService._try_parse_json(response)

                if isinstance(parsed_response, dict) and len(parsed_response) > 0:
                    # Single dict → render as block
                    response_html = ReportService._render_structured_response(
                        parsed_response, {}, "multipletext"
                    )
                    is_block = True
                elif (isinstance(parsed_response, list) and len(parsed_response) > 0
                        and isinstance(parsed_response[0], dict)):
                    # List of dicts → render as block
                    response_html = ReportService._render_structured_response(
                        parsed_response, {}, "matrixdynamic"
                    )
                    is_block = True
                else:
                    # Use unified formatter to decide how to render the response
                    response_html, is_block = ReportService._format_response_block(response)

            if is_block:
                # Complex response → question header + full-width card block
                rows_html += f"""
            <tr>
                <td colspan="2" style="font-weight: bold;">{question}</td>
                <td>{score}</td>
                <td>{module}</td>
            </tr>
            <tr>
                <td colspan="4" style="padding: 4px 8px;">{response_html}</td>
            </tr>"""
            else:
                # Simple response → standard 4-column row
                response_cell = ReportService._wrap_cell_text(
                    ReportService._escape_html(str(response_html)), 15
                )
                rows_html += f"""
            <tr>
                <td>{question}</td>
                <td>{response_cell}</td>
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
    def _build_all_responses_section(
        qa_data: List[Dict[str, str]],
        structured_question_map: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build all responses section.

        Structured questions (matrixdynamic/multipletext) are rendered as
        dynamic blocks using the survey definition. Other responses go
        through _format_response_block() which guarantees no raw JSON.
        """
        structured_question_map = structured_question_map or {}

        # Build case-insensitive lookup for structured_question_map
        struct_map_lower: Dict[str, str] = {}
        for skey in structured_question_map:
            struct_map_lower[skey.lower()] = skey

        rows_html = ""

        for idx, qa in enumerate(qa_data, 1):
            question = ReportService._escape_html(qa.get("question", ""))
            answer = qa.get("answer")
            key = qa.get("key", "")

            # Skip file upload fields
            if key.startswith("docs_"):
                continue

            # Log structured data detection for debugging
            is_complex = isinstance(answer, (list, dict)) or (
                isinstance(answer, str) and len(answer) > 10
                and any(c in answer for c in '[{')
            )
            if is_complex:
                logger.debug(
                    "AllResponses Q#%d key=%r type=%s struct_match=%s preview=%r",
                    idx, key, type(answer).__name__,
                    key in structured_question_map or key.lower() in struct_map_lower,
                    str(answer)[:120] if answer else "",
                )

            # --- Structured question detection (matrixdynamic / multipletext) ---
            # Case-insensitive lookup
            struct_info = structured_question_map.get(key)
            if not struct_info:
                canonical_key = struct_map_lower.get(key.lower())
                if canonical_key:
                    struct_info = structured_question_map.get(canonical_key)
            if struct_info:
                response_html = ReportService._render_structured_response(
                    answer, struct_info["fields"], struct_info["type"]
                )
                if not response_html:
                    response_html = "&nbsp;"
                logger.debug(
                    "AllResponses Q#%d STRUCTURED key=%r",
                    idx, key,
                )
                # Always render as full-width block row
                rows_html += f"""
            <tr>
                <td style="text-align: center; width: 8%;">{idx}</td>
                <td colspan="2" style="width: 92%; font-weight: bold; word-wrap: break-word; overflow: hidden;">{question}</td>
            </tr>
            <tr>
                <td colspan="3" style="padding: 4px 8px; overflow: hidden;">{response_html}</td>
            </tr>"""
                continue

            # --- Runtime detection: if answer is list-of-dicts or dict even without
            #     structured_question_map match, render as block ---
            answer_parsed = ReportService._try_parse_json(answer)
            if isinstance(answer_parsed, dict) and len(answer_parsed) > 0:
                response_html = ReportService._render_structured_response(
                    answer_parsed, {}, "multipletext"
                )
                if not response_html:
                    response_html = "&nbsp;"
                logger.debug(
                    "AllResponses Q#%d RUNTIME_DICT key=%r",
                    idx, key,
                )
                rows_html += f"""
            <tr>
                <td style="text-align: center; width: 8%;">{idx}</td>
                <td colspan="2" style="width: 92%; font-weight: bold; word-wrap: break-word; overflow: hidden;">{question}</td>
            </tr>
            <tr>
                <td colspan="3" style="padding: 4px 8px; overflow: hidden;">{response_html}</td>
            </tr>"""
                continue

            if (isinstance(answer_parsed, list) and len(answer_parsed) > 0
                    and isinstance(answer_parsed[0], dict)):
                response_html = ReportService._render_structured_response(
                    answer_parsed, {}, "matrixdynamic"
                )
                if not response_html:
                    response_html = "&nbsp;"
                logger.debug(
                    "AllResponses Q#%d RUNTIME_LIST key=%r",
                    idx, key,
                )
                rows_html += f"""
            <tr>
                <td style="text-align: center; width: 8%;">{idx}</td>
                <td colspan="2" style="width: 92%; font-weight: bold; word-wrap: break-word; overflow: hidden;">{question}</td>
            </tr>
            <tr>
                <td colspan="3" style="padding: 4px 8px; overflow: hidden;">{response_html}</td>
            </tr>"""
                continue

            # Use the unified formatter
            response_html, is_block = ReportService._format_response_block(answer)

            if not response_html:
                response_html = "&nbsp;"

            if is_block:
                # Complex data → question header + full-width card block
                rows_html += f"""
            <tr>
                <td style="text-align: center; width: 8%;">{idx}</td>
                <td colspan="2" style="width: 92%; font-weight: bold; word-wrap: break-word; overflow: hidden;">{question}</td>
            </tr>
            <tr>
                <td colspan="3" style="padding: 4px 8px; overflow: hidden;">{response_html}</td>
            </tr>"""
            else:
                # Simple data → standard 3-column row
                rows_html += f"""
            <tr>
                <td style="text-align: center; width: 8%;">{idx}</td>
                <td style="width: 42%; word-wrap: break-word; overflow: hidden;">{question}</td>
                <td style="width: 50%; word-wrap: break-word; overflow: hidden;">{response_html}</td>
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
    ) -> List[Dict[str, Any]]:
        """Build Q&A data with question text mapping."""
        qa_data = []

        if not user_responses:
            return qa_data

        for key, value in user_responses.items():
            # Skip None values
            if value is None:
                continue

            # Skip file upload fields
            if key.startswith("docs_"):
                continue

            # Deserialise JSON strings stored as text
            value = ReportService._try_parse_json(value)

            question_text = question_text_map.get(key, key)
            qa_data.append({
                "question": question_text,
                "answer": value,
                "key": key
            })

        return qa_data
    
    @staticmethod
    def _try_parse_json(value: Any) -> Any:
        """If value is a string that looks like a JSON array/object, parse it.

        Handles standard JSON, double-encoded JSON, Python repr format
        (single-quoted dicts/lists), BOM characters, and quoted wrappers.
        """
        if not isinstance(value, str):
            return value

        # Strip BOM and whitespace
        stripped = value.strip().lstrip('\ufeff')
        if not stripped:
            return value

        # Standard JSON parsing
        if ((stripped.startswith('[') and stripped.endswith(']'))
                or (stripped.startswith('{') and stripped.endswith('}'))):
            try:
                parsed = json.loads(stripped)
                # Double-encoded: if result is still a JSON-like string, recurse
                if isinstance(parsed, str):
                    parsed = ReportService._try_parse_json(parsed)
                return parsed
            except (json.JSONDecodeError, ValueError):
                pass

            # Fallback: ast.literal_eval for Python repr (single-quoted dicts)
            try:
                import ast
                parsed = ast.literal_eval(stripped)
                if isinstance(parsed, (list, dict)):
                    return parsed
            except (ValueError, SyntaxError):
                pass

            logger.debug(
                "_try_parse_json: failed to parse string starting with %r (len=%d)",
                stripped[:50], len(stripped),
            )

        # Handle quoted JSON wrappers: '"[...]"' or "'[...]'"
        if ((stripped.startswith('"') and stripped.endswith('"'))
                or (stripped.startswith("'") and stripped.endswith("'"))):
            inner = stripped[1:-1]
            result = ReportService._try_parse_json(inner)
            if not isinstance(result, str):
                return result

        # Last resort: try to find embedded JSON within the string
        # (handles prefixed text like "Response: [{...}]")
        for start_char, end_char in [('[', ']'), ('{', '}')]:
            start_idx = stripped.find(start_char)
            end_idx = stripped.rfind(end_char)
            if start_idx >= 0 and end_idx > start_idx:
                fragment = stripped[start_idx:end_idx + 1]
                try:
                    parsed = json.loads(fragment)
                    if isinstance(parsed, (list, dict)):
                        return parsed
                except (json.JSONDecodeError, ValueError):
                    pass

        return value

    @staticmethod
    def _format_value_readable(value: Any) -> str:
        """Recursively convert a dict/list/scalar to human-readable text.

        Used as a replacement for ``json.dumps()`` so that nested
        structures display as readable prose instead of raw JSON.
        """
        if value is None or value == "":
            return ""
        if isinstance(value, dict):
            parts = []
            for k, v in value.items():
                label = ReportService._humanize_label(str(k))
                parts.append(f"{label}: {ReportService._format_value_readable(v)}")
            return ", ".join(parts)
        if isinstance(value, (list, tuple)):
            items = [ReportService._format_value_readable(item) for item in value]
            return "; ".join(items)
        return str(value)

    @staticmethod
    def _humanize_label(slug: str) -> str:
        """Convert field_name or camelCase to Field Name."""
        # Split camelCase boundaries: "grossWeekly" → "gross Weekly"
        spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', slug)
        # Handle consecutive uppercase: "HTMLParser" → "HTML Parser"
        spaced = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', spaced)
        return spaced.replace('_', ' ').replace('-', ' ').title()

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

        # Deserialise JSON strings so type checks below work correctly
        answer = ReportService._try_parse_json(answer)

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
                    item_str = ReportService._format_value_readable(item)
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

        # Deserialise JSON strings so type checks below work correctly
        answer = ReportService._try_parse_json(answer)

        # Matrix: list of dicts → one line per row
        if (isinstance(answer, list) and len(answer) > 0
                and isinstance(answer[0], dict)):
            lines: list[str] = []
            for i, row in enumerate(answer, 1):
                if not isinstance(row, dict):
                    continue
                pairs = ", ".join(
                    f"{ReportService._escape_html(ReportService._humanize_label(str(k)))}: "
                    f"{ReportService._escape_html(str(v))}"
                    for k, v in row.items()
                    if v is not None and v != ""
                )
                if pairs:
                    prefix = f"Entry {i}: " if len(answer) > 1 else ""
                    lines.append(ReportService._wrap_cell_text(f"{prefix}{pairs}", 55))
            return "<br/><br/>".join(lines) if lines else ""

        # Dict → key: value per line (use wider wrap for response column)
        if isinstance(answer, dict):
            lines = []
            for k, v in answer.items():
                key_label = ReportService._escape_html(
                    ReportService._humanize_label(str(k))
                )
                val_str = ReportService._escape_html(str(v))
                lines.append(ReportService._wrap_cell_text(f"{key_label}: {val_str}", 55))
            return "<br/>".join(lines)

        # Simple list/tuple → one item per line
        if isinstance(answer, (list, tuple)):
            items = []
            for item in answer:
                if isinstance(item, (dict, list)):
                    item_str = ReportService._format_value_readable(item)
                else:
                    item_str = str(item)
                items.append(ReportService._wrap_cell_text(ReportService._escape_html(item_str)))
            return "<br/>".join(items)

        # Scalar
        if isinstance(answer, str):
            return ReportService._wrap_cell_text(ReportService._escape_html(answer))

        return ReportService._wrap_cell_text(ReportService._escape_html(str(answer)))

    @staticmethod
    def _format_response_block(answer: Any) -> tuple:
        """Unified response formatter that NEVER returns raw JSON.

        Returns a tuple (html, is_block):
        - html: formatted HTML string
        - is_block: True if the output is a multi-line card block that needs
          a full-width colspan row; False if it fits in a normal cell.
        """
        # Step 1: parse JSON strings
        answer = ReportService._try_parse_json(answer)

        # Step 2: list of dicts → columnar table
        if (isinstance(answer, list) and len(answer) > 0
                and isinstance(answer[0], dict)):
            rows = [r for r in answer if isinstance(r, dict)]
            if rows:
                table_html = ReportService._render_dicts_as_columnar_table(rows)
                return (table_html, True)
            return ("&nbsp;", False)

        # Step 3: dict → single-row columnar table
        if isinstance(answer, dict) and len(answer) >= 1:
            table_html = ReportService._render_dicts_as_columnar_table([answer])
            return (table_html, True)

        # Step 4: simple list → comma-separated
        if isinstance(answer, list) and len(answer) > 0:
            items = [ReportService._escape_html(str(item))
                     for item in answer if item is not None and item != ""]
            text = ", ".join(items) if items else "&nbsp;"
            return (ReportService._wrap_cell_text(text, 55), False)

        # Step 5: string that still looks like JSON → regex extraction
        if isinstance(answer, str) and len(answer) > 20:
            stripped = answer.strip()
            if ((stripped.startswith('[') and stripped.endswith(']'))
                    or (stripped.startswith('{') and stripped.endswith('}'))):
                return (ReportService._format_unparseable_json_string(answer), True)

        # Step 6: scalar
        if answer is None or answer == "":
            return ("&nbsp;", False)
        text = ReportService._wrap_cell_text(ReportService._escape_html(str(answer)), 55)
        return (text, False)

    @staticmethod
    def _render_structured_response(
        answer: Any,
        field_map: Dict[str, str],
        question_type: str
    ) -> str:
        """Render a matrixdynamic or multipletext response as a columnar table.

        Args:
            answer: The response value (list of dicts, dict, or string-encoded JSON)
            field_map: Mapping of field keys to human-readable titles
            question_type: "matrixdynamic" or "multipletext"

        Returns:
            Formatted HTML string (always block-level, never raw JSON)
        """
        # Aggressively parse string-encoded data
        answer = ReportService._try_parse_json(answer)
        if isinstance(answer, str):
            # Second attempt: strip outer quotes and retry
            stripped = answer.strip()
            if ((stripped.startswith('"') and stripped.endswith('"'))
                    or (stripped.startswith("'") and stripped.endswith("'"))):
                answer = ReportService._try_parse_json(stripped[1:-1])

        def _field_label(key: str) -> str:
            """Get human-readable label from field_map, falling back to humanize."""
            return field_map.get(key, ReportService._humanize_label(str(key)))

        # matrixdynamic → list of dicts → columnar table
        if question_type == "matrixdynamic":
            if isinstance(answer, list) and len(answer) > 0:
                rows = [r for r in answer if isinstance(r, dict)]
                if rows:
                    return ReportService._render_dicts_as_columnar_table(rows, field_map)
            # Fallback: if data is a single dict, render as single-row table
            if isinstance(answer, dict):
                return ReportService._render_dicts_as_columnar_table([answer], field_map)

        # multipletext → single dict → columnar table (keys as columns)
        if question_type == "multipletext":
            if isinstance(answer, dict):
                return ReportService._render_dicts_as_columnar_table([answer], field_map)
            # Fallback: if stored as a list with one dict
            if isinstance(answer, list) and len(answer) == 1 and isinstance(answer[0], dict):
                return ReportService._render_dicts_as_columnar_table([answer[0]], field_map)

        # Final fallback: use _format_response_block for anything else
        html, _ = ReportService._format_response_block(answer)
        return html

    @staticmethod
    def _render_dicts_as_columnar_table(
        rows: List[Dict[str, Any]],
        field_map: Optional[Dict[str, str]] = None
    ) -> str:
        """Render a list of dicts as a horizontal columnar table.

        Each dict key becomes a column header; each dict becomes a row.
        For a single dict like {"Monday": "9-5", "Tuesday": "9-5", ...},
        this produces a table with day-name columns and values in one row.

        Args:
            rows: List of dicts to render as table rows
            field_map: Optional mapping of field keys to human-readable titles
        """
        if not rows:
            return "&nbsp;"

        field_map = field_map or {}

        # Collect all unique keys preserving insertion order
        seen: dict[str, None] = {}
        for row in rows:
            for k in row:
                if k not in seen:
                    seen[k] = None
        columns = list(seen.keys())

        if not columns:
            return "&nbsp;"

        def _label(key: str) -> str:
            return field_map.get(key, ReportService._humanize_label(str(key)))

        def _cell_value(val: Any) -> str:
            if val is None or val == "":
                return "&nbsp;"
            if isinstance(val, (dict, list)):
                return ReportService._escape_html(
                    ReportService._format_value_readable(val)
                )
            return ReportService._escape_html(str(val))

        # Build header row
        header_cells = "".join(
            f'<th style="text-align: center; font-size: 12px; padding: 4px 6px;">'
            f'{ReportService._escape_html(_label(c))}</th>'
            for c in columns
        )

        # Build data rows
        body_rows = ""
        for row in rows:
            cells = "".join(
                f'<td style="text-align: center; font-size: 12px; padding: 4px 6px;">'
                f'{_cell_value(row.get(c))}</td>'
                for c in columns
            )
            body_rows += f"<tr>{cells}</tr>"

        return (
            f'<table class="sub-table" style="table-layout: auto; width: 100%; '
            f'border-collapse: collapse; margin: 4px 0;">'
            f'<thead><tr>{header_cells}</tr></thead>'
            f'<tbody>{body_rows}</tbody>'
            f'</table>'
        )

    @staticmethod
    def _format_unparseable_json_string(text: str) -> str:
        """Best-effort formatting of a string that looks like JSON but failed parsing.

        Extracts "key":"value" pairs using regex and renders them as readable
        Key: Value lines.  Falls back to word-wrapped plain text.
        """
        pairs = re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', text)
        if pairs:
            lines = []
            for key, val in pairs:
                label = ReportService._humanize_label(key)
                lines.append(
                    ReportService._wrap_cell_text(
                        f"{ReportService._escape_html(label)}: {ReportService._escape_html(val)}",
                        55,
                    )
                )
            return "<br/>".join(lines)

        # Fallback: just wrap the raw text
        return ReportService._wrap_cell_text(ReportService._escape_html(text), 55)

    @staticmethod
    def _format_matrix_as_table(answer: List[Dict[str, Any]]) -> str:
        """Render a matrix response (list of dicts) as an HTML sub-table.

        Each dict key becomes a column header; each list item becomes a row.
        For tables with 6+ columns, switches to a vertical card layout
        (one card per row, two-column key/value table) to avoid cramming.
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

        # For wide tables (6+ columns) OR tables with very long values,
        # use vertical card layout to avoid cramming
        use_cards = len(columns) >= 6
        if not use_cards:
            # Check if any cell value is very long (would overflow horizontal table)
            for row in answer:
                if not isinstance(row, dict):
                    continue
                total_chars = sum(len(str(row.get(c, ""))) for c in columns)
                if total_chars > 120 or any(len(str(row.get(c, ""))) > 60 for c in columns):
                    use_cards = True
                    break
        if use_cards:
            return ReportService._format_matrix_as_cards(answer, columns)

        # Render narrow matrices as plain text (bold headers + values)
        # instead of nested <table> elements to avoid xhtml2pdf crashes.
        total = len([r for r in answer if isinstance(r, dict)])
        col_max = 50

        blocks: list[str] = []
        entry_num = 0
        for row in answer:
            if not isinstance(row, dict):
                continue
            entry_num += 1
            lines: list[str] = []

            if total > 1:
                lines.append(
                    f'<b style="font-size: 12px; background-color: #e8e8e8;">'
                    f'Entry {entry_num} of {total}</b>'
                )

            for c in columns:
                val = row.get(c, "")
                if val is None or val == "":
                    continue
                label = ReportService._escape_html(ReportService._humanize_label(str(c)))
                if isinstance(val, (dict, list)):
                    display = ReportService._wrap_cell_text(
                        ReportService._escape_html(ReportService._format_value_readable(val)), col_max
                    )
                else:
                    display = ReportService._wrap_cell_text(
                        ReportService._escape_html(str(val)), col_max
                    )
                lines.append(f'<b style="font-size: 12px;">{label}:</b> '
                             f'<span style="font-size: 12px;">{display}</span>')

            blocks.append("<br/>".join(lines))

        return "<br/><br/>".join(blocks)

    @staticmethod
    def _format_matrix_as_cards(
        answer: List[Dict[str, Any]], columns: List[str]
    ) -> str:
        """Render a wide matrix as vertical cards (one per row).

        Each entry is shown as a two-column key/value mini-table with a
        header like "Entry 1 of N".  This avoids the cramped horizontal
        layout when there are many fields (e.g. staff details with 8+ keys).
        """
        total = len([r for r in answer if isinstance(r, dict)])
        cards: list[str] = []
        entry_num = 0

        for row in answer:
            if not isinstance(row, dict):
                continue
            entry_num += 1
            rows_html = ""
            for c in columns:
                val = row.get(c, "")
                if val is None or val == "":
                    continue
                label = ReportService._escape_html(ReportService._humanize_label(str(c)))
                if isinstance(val, (dict, list)):
                    display = ReportService._wrap_cell_text(
                        ReportService._escape_html(ReportService._format_value_readable(val)), 50
                    )
                else:
                    display = ReportService._wrap_cell_text(
                        ReportService._escape_html(str(val)), 50
                    )
                rows_html += (
                    f'<tr>'
                    f'<td style="font-size: 12px; font-weight: bold; width: 30%; vertical-align: top;">{label}</td>'
                    f'<td style="font-size: 12px; width: 70%; vertical-align: top;">{display}</td>'
                    f'</tr>'
                )

            header = f"Entry {entry_num} of {total}" if total > 1 else ""
            header_html = (
                f'<tr><td colspan="2" style="font-size: 12px; font-weight: bold; '
                f'background-color: #e8e8e8; padding: 4px 6px;">{header}</td></tr>'
                if header else ""
            )

            cards.append(
                f'<table class="sub-table" style="table-layout: fixed; width: 100%; margin-bottom: 6px;">'
                f"{header_html}{rows_html}</table>"
            )

        return "".join(cards)

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

            @frame header_frame {
                -pdf-frame-content: page-header;
                top: 0.5cm;
                margin-left: 1cm;
                margin-right: 1cm;
                height: 2cm;
            }
        }

        /* Cover Page */
        .cover-page {
            text-align: center;
        }

        .cover-header-line {
            font-size: 11px;
            color: #666666;
            text-align: right;
            margin-bottom: 5px;
            margin-top: 0;
        }

        .cover-rule {
            border: none;
            border-top: 2px solid #2c3e6b;
            margin: 10px 0 0 0;
        }

        .cover-firm-spaced {
            font-size: 13px;
            font-weight: bold;
            color: #2c3e6b;
            letter-spacing: 4px;
            text-align: center;
            margin-top: 120px;
            margin-bottom: 8px;
        }

        .cover-title {
            font-size: 32px;
            font-weight: bold;
            color: #2c3e6b;
            text-align: center;
            margin-top: 5px;
            margin-bottom: 50px;
            line-height: 1.2;
        }

        .cover-business-name {
            font-size: 22px;
            font-weight: bold;
            color: #3366a0;
            text-align: center;
            margin-bottom: 10px;
        }

        .cover-prepared-for {
            font-size: 15px;
            color: #333333;
            text-align: center;
            margin-bottom: 5px;
        }

        .cover-meta {
            font-size: 14px;
            color: #333333;
            text-align: center;
            margin-bottom: 40px;
        }

        .cover-confidential {
            font-size: 14px;
            font-weight: bold;
            color: #cc0000;
            letter-spacing: 3px;
            text-align: center;
            margin-top: 30px;
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
            padding: 6px 8px;
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
            padding: 5px 6px;
            text-align: left;
            color: #000000;
            font-size: inherit;
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
    def _strip_response_tables_from_summary(html: str) -> str:
        """Remove redundant response-data tables from the AI client summary.

        The AI scoring prompt often embeds a full "All Responses" table inside
        the client summary markdown.  These tables contain raw JSON values and
        are redundant with the dedicated All Responses section.  We identify
        them in three ways:

        1. Heading-based: any <hN> containing "All Responses" / "User Responses"
           followed by a <table>.
        2. Column-based: any <table> whose first row of <th> cells includes
           both "Question" and "Response" headers.
        3. Cell-based: any remaining <td> containing raw JSON gets formatted
           using _format_response_block().
        """
        # --- Pass 1: strip heading + table by heading text ---
        html = re.sub(
            r'<h[1-6][^>]*>[^<]*?(?:All|User|Complete|Scored)\s+Responses[^<]*?</h[1-6]>'
            r'(?:\s*<table[^>]*>.*?</table>)?',
            '',
            html,
            flags=re.S | re.I,
        )
        # Also strip "Scoring Detail" heading (orphaned after table removal)
        html = re.sub(
            r'<h[1-6][^>]*>[^<]*?Scoring\s+Detail[^<]*?</h[1-6]>',
            '',
            html,
            flags=re.S | re.I,
        )

        # --- Pass 2: strip tables whose headers include Question + Response ---
        def _is_response_data_table(match: re.Match) -> str:
            table_html = match.group(0)
            # Extract header cells
            headers = re.findall(r'<th[^>]*>(.*?)</th>', table_html, re.S | re.I)
            header_text = ' '.join(h.strip().lower() for h in headers)
            if 'question' in header_text and 'response' in header_text:
                # Also strip any immediately preceding heading
                return ''
            return table_html

        html = re.sub(
            r'<table(?![^>]*\bclass=)[^>]*>.*?</table>',
            _is_response_data_table,
            html,
            flags=re.S,
        )

        # --- Pass 3: format raw JSON in any surviving <td> cells ---
        def _format_cell(match: re.Match) -> str:
            attrs = match.group(1) or ''
            content = match.group(2)
            stripped = content.strip()
            # Skip cells that already contain HTML formatting
            if '<b ' in stripped or '<span ' in stripped or '<br' in stripped:
                return match.group(0)
            # Check for JSON-like content
            if not stripped:
                return match.group(0)
            if (stripped[0] in '[{' and stripped[-1] in ']}'):
                parsed = ReportService._try_parse_json(stripped)
                if isinstance(parsed, (dict, list)):
                    formatted, _ = ReportService._format_response_block(parsed)
                    if formatted and formatted != '&nbsp;':
                        return f'<td{attrs}>{formatted}</td>'
            return match.group(0)

        html = re.sub(r'<td([^>]*)>(.*?)</td>', _format_cell, html, flags=re.S)

        return html

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