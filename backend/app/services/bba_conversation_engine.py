"""
BBA Conversation Engine Service
Manages the BBA diagnostic report generation workflow through Steps 3-7.
"""
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
import json
import logging
import re
from pathlib import Path

# from app.services.openai_service import OpenAIService  # Preserved for rollback
from app.services.claude_service import ClaudeService
from app.services.scoring_service import ScoringService
from app.models.bba import BBA

logger = logging.getLogger(__name__)


def load_bba_prompt(prompt_name: str) -> str:
    """
    Load a BBA prompt template from the prompts directory.
    
    Args:
        prompt_name: Name of the prompt file (without .md extension)
        
    Returns:
        Prompt content as string
    """
    prompt_path = Path(__file__).resolve().parents[2] / "files" / "prompts" / "bba" / f"{prompt_name}.md"
    
    if not prompt_path.exists():
        logger.error(f"Prompt file not found: {prompt_path}")
        raise FileNotFoundError(f"Prompt file not found: {prompt_name}.md")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


class BBAConversationEngine:
    """
    Manages the BBA report generation workflow.
    
    This engine guides advisors through:
    - Step 3: Draft Findings (analyze files, propose Top 10 findings)
    - Step 4: Expand Findings (write full paragraphs for each finding)
    - Step 5: Snapshot Table (generate 3-column summary table)
    - Step 6: 12-Month Plan (detailed recommendations)
    - Step 7: Review & Edit (apply edits and refinements)
    """
    
    def __init__(self):
        """Initialize the conversation engine with Claude service."""
        self.openai_service = ClaudeService()
    
    def _build_context_from_bba(self, bba: BBA) -> Dict[str, Any]:
        """
        Build context dictionary from BBA model for prompts.
        
        Args:
            bba: BBA model instance
            
        Returns:
            Dictionary containing all relevant context
        """
        ctx = {
            "client_name": bba.client_name or "Unknown Client",
            "industry": bba.industry or "Unknown Industry",
            "company_size": bba.company_size or "Unknown",
            "locations": bba.locations or "Not specified",
            "exclusions": bba.exclusions or "None",
            "constraints": bba.constraints or "None",
            "preferred_ranking": bba.preferred_ranking or "By materiality and impact",
            "strategic_priorities": bba.strategic_priorities or "Not specified",
            "exclude_sale_readiness": bba.exclude_sale_readiness,
            "file_ids": bba.file_ids or [],
            "file_mappings": bba.file_mappings or {},
        }
        if getattr(bba, "diagnostic_context", None):
            ctx["diagnostic_context"] = bba.diagnostic_context
        engagement = getattr(bba, "engagement", None)
        ctx["engagement_tool"] = engagement.tool if engagement else None
        return ctx

    def _build_value_builder_taxonomy_block(self) -> str:
        """
        Instruction block constraining `priority_area` to the canonical Value
        Builder module taxonomy, so BBA findings can be mapped 1:1 to
        Program Guide modules without fuzzy text matching. Generated from
        ScoringService.VALUE_BUILDER_MODULES at call time (single source of
        truth) rather than a static duplicate prompt file.
        """
        names = "\n".join(f"- {name}" for name in ScoringService.VALUE_BUILDER_MODULES.values())
        return (
            "\n\n## Value Builder Module Taxonomy (REQUIRED)\n"
            "This is a Value Builder engagement. Every finding's `priority_area` MUST be set to "
            "exactly one of the following category names, verbatim (do not invent new categories "
            "or reword these):\n\n" + names +
            "\n\nIf a finding spans multiple areas, choose the single most dominant one."
        )

    def _maybe_add_value_builder_taxonomy(self, system_blocks: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        """Append the Value Builder taxonomy block in place when applicable."""
        if context.get("engagement_tool") == "value_builder":
            system_blocks.append({
                "type": "text",
                "text": self._build_value_builder_taxonomy_block(),
                "cache_control": {"type": "ephemeral"},
            })
    
    def _separate_files_by_type(self, file_mappings: Dict[str, str]) -> Tuple[List[str], List[str]]:
        """
        Separate file IDs by type for proper OpenAI API routing.
        
        PDFs can be attached as input_file in messages.
        CSV/TXT/XLSX/etc. must go through Code Interpreter container.
        
        Args:
            file_mappings: Dictionary mapping filename to file_id
            
        Returns:
            Tuple of (pdf_file_ids, ci_file_ids)
        """
        pdf_ext = {"pdf"}
        ci_ext = {"csv", "txt", "text", "md", "markdown", "json", "xml", "yaml", "yml", "xlsx", "xls"}
        
        pdf_file_ids = []
        ci_file_ids = []
        
        for filename, file_id in file_mappings.items():
            if not file_id:
                continue
            
            ext = Path(filename).suffix.lower().lstrip('.')
            
            if ext in pdf_ext:
                pdf_file_ids.append(file_id)
            elif ext in ci_ext:
                ci_file_ids.append(file_id)
            else:
                # Unknown extension - default to Code Interpreter
                logger.warning(f"[BBA Engine] Unknown file extension '{ext}' for {filename}, treating as Code Interpreter file")
                ci_file_ids.append(file_id)
        
        return pdf_file_ids, ci_file_ids
    
    async def generate_draft_findings(
        self, 
        bba: BBA,
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Step 3: Generate draft findings from uploaded files.
        
        Analyzes all uploaded documents and proposes a ranked list of 
        top 10 findings with one-line summaries.
        
        Args:
            bba: BBA model with files and questionnaire data
            custom_instructions: Optional additional instructions from advisor
            
        Returns:
            Dictionary containing:
            - findings: List of ranked findings with summaries
            - tokens_used: Token count
            - model: Model used
        """
        logger.info(f"[BBA Engine] Generating draft findings for BBA {bba.id}")
        
        context = self._build_context_from_bba(bba)
        
        # Load system prompt and step-specific prompt
        try:
            system_prompt = load_bba_prompt("bba_system_prompt")
            step_prompt = load_bba_prompt("step3_draft_findings")
        except FileNotFoundError as e:
            logger.error(f"[BBA Engine] Failed to load prompts: {e}")
            raise
        
        # Two separately-cached blocks: base prompt hits cache across all steps;
        # step prompt hits cache on repeated Step 3 calls within the same session.
        system_blocks = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": step_prompt, "cache_control": {"type": "ephemeral"}},
        ]
        self._maybe_add_value_builder_taxonomy(system_blocks, context)

        # Build optional prior diagnostic section when BBA was created from a diagnostic.
        # Capped at MAX_DIAGNOSTIC_CHARS to prevent full HTML reports (50–500 KB) from
        # consuming 12K–125K extra input tokens on every Step 3 call.
        MAX_DIAGNOSTIC_CHARS = 6000
        diagnostic_section = ""
        if context.get("diagnostic_context"):
            dc = context["diagnostic_context"]
            report_html = dc.get("report_html") if isinstance(dc, dict) else None
            ai_analysis = dc.get("ai_analysis") if isinstance(dc, dict) else None
            if report_html:
                plain = re.sub(r'<[^>]+>', ' ', report_html)
                plain = re.sub(r'\s+', ' ', plain).strip()
                diagnostic_section = f"\n\n## Prior Diagnostic Report (use as context)\n{plain[:MAX_DIAGNOSTIC_CHARS]}\n"
            elif ai_analysis:
                advisor_report = ai_analysis.get("advisorReport", "") if isinstance(ai_analysis, dict) else ""
                text = advisor_report or json.dumps(ai_analysis)
                diagnostic_section = f"\n\n## Prior Diagnostic Report (use as context)\n{text[:MAX_DIAGNOSTIC_CHARS]}\n"

        # Build user message with context
        user_content = f"""
Analyse the uploaded files and generate draft findings for this client.
{diagnostic_section}

## Client Context
- Client Name: {context['client_name']}
- Industry: {context['industry']}
- Company Size: {context['company_size']}
- Locations: {context['locations']}
- Strategic Priorities: {context['strategic_priorities']}
- Exclusions: {context['exclusions']}
- Constraints: {context['constraints']}
- Exclude Sale-Readiness: {'Yes' if context['exclude_sale_readiness'] else 'No'}
- Preferred Ranking: {context['preferred_ranking']}

## Uploaded Files
{json.dumps(context['file_mappings'], separators=(',', ':'))}

{f"## Additional Instructions from Advisor{chr(10)}{custom_instructions}" if custom_instructions else ""}

Please analyse all uploaded files and generate a ranked list of Top 10 findings.
Return your response as a JSON object.
"""

        messages = [
            {"role": "user", "content": user_content}
        ]
        
        # Separate files by type: PDFs go as input_file, CSV/TXT/XLSX go to Code Interpreter
        file_mappings = context['file_mappings'] or {}
        pdf_file_ids, ci_file_ids = self._separate_files_by_type(file_mappings)
        
        logger.info(f"[BBA Engine] File categorization: {len(pdf_file_ids)} PDF(s) for input_file, {len(ci_file_ids)} file(s) for Code Interpreter")
        
        # Build tools parameter for Code Interpreter if needed
        tools = None
        if ci_file_ids:
            tools = [{
                "type": "code_interpreter",
                "container": {
                    "type": "auto",
                    "file_ids": ci_file_ids
                }
            }]
        
        try:
            result = await self.openai_service.generate_json_completion(
                messages=messages,
                system_blocks=system_blocks,
                file_ids=pdf_file_ids if pdf_file_ids else None,  # Only PDFs as input_file
                tools=tools,  # CSV/TXT/XLSX go to Code Interpreter
                reasoning_effort="medium",
                max_output_tokens=16384,
            )

            logger.info(f"[BBA Engine] Draft findings generated successfully")
            
            return {
                "findings": result.get("parsed_content", {}),
                "raw_content": result.get("content", ""),
                "tokens_used": result.get("tokens_used", 0),
                "model": result.get("model", "")
            }
            
        except Exception as e:
            logger.error(f"[BBA Engine] Failed to generate draft findings: {e}", exc_info=True)
            raise
    
    async def expand_findings(
        self, 
        bba: BBA,
        findings_to_expand: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Step 4: Expand findings into full paragraphs.
        
        Takes the draft findings and writes 1-3 paragraphs per finding
        describing the issue and its implications.
        
        Args:
            bba: BBA model with draft findings
            findings_to_expand: Optional custom list of findings to expand
            
        Returns:
            Dictionary containing expanded findings
        """
        logger.info(f"[BBA Engine] Expanding findings for BBA {bba.id}")
        
        context = self._build_context_from_bba(bba)
        
        # Use provided findings or get from BBA
        findings = findings_to_expand or bba.draft_findings
        if not findings:
            raise ValueError("No draft findings available to expand")
        
        # Load prompts
        try:
            system_prompt = load_bba_prompt("bba_system_prompt")
            step_prompt = load_bba_prompt("step4_expand_findings")
        except FileNotFoundError as e:
            logger.error(f"[BBA Engine] Failed to load prompts: {e}")
            raise
        
        system_blocks = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": step_prompt, "cache_control": {"type": "ephemeral"}},
        ]
        self._maybe_add_value_builder_taxonomy(system_blocks, context)

        user_content = f"""
Expand the following draft findings into full paragraphs.

## Client Context
- Client Name: {context['client_name']}
- Industry: {context['industry']}
- Strategic Priorities: {context['strategic_priorities']}

## Draft Findings to Expand
{json.dumps(findings, separators=(',', ':'))}

Return your response as a JSON object.
"""

        messages = [
            {"role": "user", "content": user_content}
        ]

        # No file attachments needed — draft findings already contain all extracted insights.
        # Re-attaching files would force the model to re-read every PDF/CSV, adding 30-120s.
        try:
            result = await self.openai_service.generate_json_completion(
                messages=messages,
                system_blocks=system_blocks,
                reasoning_effort="low",
                max_output_tokens=12288,
            )

            logger.info(f"[BBA Engine] Findings expanded successfully")
            
            return {
                "expanded_findings": result.get("parsed_content", {}),
                "raw_content": result.get("content", ""),
                "tokens_used": result.get("tokens_used", 0),
                "model": result.get("model", "")
            }
            
        except Exception as e:
            logger.error(f"[BBA Engine] Failed to expand findings: {e}", exc_info=True)
            raise
    
    async def generate_snapshot_table(
        self, 
        bba: BBA
    ) -> Dict[str, Any]:
        """
        Step 5: Generate the Key Findings & Recommendations Snapshot table.
        
        Creates a concise three-column table:
        Priority Area | Key Findings | Recommendations
        
        Args:
            bba: BBA model with expanded findings
            
        Returns:
            Dictionary containing the snapshot table data
        """
        logger.info(f"[BBA Engine] Generating snapshot table for BBA {bba.id}")
        
        context = self._build_context_from_bba(bba)
        
        # Get expanded findings
        expanded_findings = bba.expanded_findings
        if not expanded_findings:
            raise ValueError("No expanded findings available for snapshot table")
        
        # Load prompts
        try:
            system_prompt = load_bba_prompt("bba_system_prompt")
            step_prompt = load_bba_prompt("step5_snapshot_table")
        except FileNotFoundError as e:
            logger.error(f"[BBA Engine] Failed to load prompts: {e}")
            raise
        
        system_blocks = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": step_prompt, "cache_control": {"type": "ephemeral"}},
        ]
        self._maybe_add_value_builder_taxonomy(system_blocks, context)

        user_content = f"""
Generate the Key Findings & Recommendations Snapshot table.

## Client Context
- Client Name: {context['client_name']}
- Industry: {context['industry']}

## Expanded Findings
{json.dumps(expanded_findings, separators=(',', ':'))}

Return your response as a JSON object.
"""

        messages = [
            {"role": "user", "content": user_content}
        ]

        try:
            result = await self.openai_service.generate_json_completion(
                messages=messages,
                system_blocks=system_blocks,
                reasoning_effort="low",
                max_output_tokens=8192,
            )

            logger.info(f"[BBA Engine] Snapshot table generated successfully")
            
            return {
                "snapshot_table": result.get("parsed_content", {}),
                "raw_content": result.get("content", ""),
                "tokens_used": result.get("tokens_used", 0),
                "model": result.get("model", "")
            }
            
        except Exception as e:
            logger.error(f"[BBA Engine] Failed to generate snapshot table: {e}", exc_info=True)
            raise
    
    async def generate_12month_plan(
        self, 
        bba: BBA
    ) -> Dict[str, Any]:
        """
        Step 6: Generate the 12-Month Recommendations Plan.
        
        For each finding, creates a recommendation with:
        - Purpose
        - Key Objectives (3-5 bullets)
        - Actions to Complete (5-10 points)
        - BBA Support Outline
        - Expected Outcomes
        
        Args:
            bba: BBA model with snapshot table
            
        Returns:
            Dictionary containing the 12-month plan
        """
        logger.info(f"[BBA Engine] Generating 12-month plan for BBA {bba.id}")
        
        context = self._build_context_from_bba(bba)
        
        # Get expanded findings and snapshot table
        expanded_findings = bba.expanded_findings
        snapshot_table = bba.snapshot_table
        
        if not expanded_findings:
            raise ValueError("No expanded findings available for 12-month plan")
        
        # Load prompts
        try:
            system_prompt = load_bba_prompt("bba_system_prompt")
            step_prompt = load_bba_prompt("step6_12month_plan")
        except FileNotFoundError as e:
            logger.error(f"[BBA Engine] Failed to load prompts: {e}")
            raise
        
        system_blocks = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": step_prompt, "cache_control": {"type": "ephemeral"}},
        ]

        user_content = f"""
Generate the 12-Month Recommendations Plan.

## Client Context
- Client Name: {context['client_name']}
- Industry: {context['industry']}
- Strategic Priorities: {context['strategic_priorities']}

## Expanded Findings
{json.dumps(expanded_findings, separators=(',', ':'))}

## Snapshot Table
{json.dumps(snapshot_table, separators=(',', ':')) if snapshot_table else "Not yet generated"}

Return your response as a JSON object.
"""

        messages = [
            {"role": "user", "content": user_content}
        ]

        # No file attachments needed — expanded findings and snapshot table
        # already contain all detail. Re-attaching files adds 30-120s of re-processing.
        try:
            result = await self.openai_service.generate_json_completion(
                messages=messages,
                system_blocks=system_blocks,
                reasoning_effort="low",
                max_output_tokens=32768,
            )

            logger.info(f"[BBA Engine] 12-month plan generated successfully")
            
            return {
                "twelve_month_plan": result.get("parsed_content", {}),
                "raw_content": result.get("content", ""),
                "tokens_used": result.get("tokens_used", 0),
                "model": result.get("model", "")
            }
            
        except Exception as e:
            logger.error(f"[BBA Engine] Failed to generate 12-month plan: {e}", exc_info=True)
            raise
    
    def _select_edit_sections(self, bba: BBA, edits: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return only the report sections relevant to the requested edits to avoid
        sending all 4 sections (~20-40K tokens) on every single edit call.
        draft_findings is always included as a lightweight anchor.
        Falls back to all sections if no keywords match.
        """
        edit_text = json.dumps(edits).lower()
        sections: Dict[str, Any] = {"draft_findings": bba.draft_findings}

        if any(kw in edit_text for kw in ("expanded", "findings", "paragraph", "finding")):
            sections["expanded_findings"] = bba.expanded_findings
        if any(kw in edit_text for kw in ("snapshot", "table", "priority area")):
            sections["snapshot_table"] = bba.snapshot_table
        if any(kw in edit_text for kw in ("plan", "recommendation", "action", "month", "timing", "objective", "outcome")):
            sections["twelve_month_plan"] = bba.twelve_month_plan

        # Fallback: include all sections if no specific keywords matched
        if len(sections) == 1:
            sections["expanded_findings"] = bba.expanded_findings
            sections["snapshot_table"] = bba.snapshot_table
            sections["twelve_month_plan"] = bba.twelve_month_plan

        included = [k for k in sections if k != "draft_findings"]
        logger.info(f"[BBA Engine] Step 7 context sections: {included or ['fallback: all']}")
        return sections

    async def apply_edits(
        self,
        bba: BBA,
        edits: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 7: Apply edits to the report.
        
        Handles edit requests such as:
        - Re-ranking findings
        - Adjusting timing
        - Changing language
        - Adding/removing recommendations
        
        Args:
            bba: BBA model with all report data
            edits: Dictionary describing the requested edits
            
        Returns:
            Dictionary containing the updated report sections
        """
        logger.info(f"[BBA Engine] Applying edits for BBA {bba.id}")
        
        context = self._build_context_from_bba(bba)
        
        # Load prompts
        try:
            system_prompt = load_bba_prompt("bba_system_prompt")
            step_prompt = load_bba_prompt("step7_review_edit")
        except FileNotFoundError as e:
            logger.error(f"[BBA Engine] Failed to load prompts: {e}")
            raise
        
        system_blocks = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": step_prompt, "cache_control": {"type": "ephemeral"}},
        ]

        # Only pass sections relevant to the edit to avoid sending 20-40K tokens of
        # unrelated report data on every single advisor edit call.
        current_report = self._select_edit_sections(bba, edits)

        user_content = f"""
Apply the following edits to the report.

## Client Context
- Client Name: {context['client_name']}
- Industry: {context['industry']}

## Current Report State (sections relevant to this edit)
{json.dumps(current_report, separators=(',', ':'))}

## Requested Edits
{json.dumps(edits, separators=(',', ':'))}

Return the updated sections as a JSON object.
"""

        messages = [
            {"role": "user", "content": user_content}
        ]

        try:
            result = await self.openai_service.generate_json_completion(
                messages=messages,
                system_blocks=system_blocks,
                reasoning_effort="low",
                max_output_tokens=24576,
            )

            logger.info(f"[BBA Engine] Edits applied successfully")
            
            return {
                "updated_report": result.get("parsed_content", {}),
                "raw_content": result.get("content", ""),
                "tokens_used": result.get("tokens_used", 0),
                "model": result.get("model", "")
            }
            
        except Exception as e:
            logger.error(f"[BBA Engine] Failed to apply edits: {e}", exc_info=True)
            raise
    
    async def generate_executive_summary(
        self, 
        bba: BBA
    ) -> Dict[str, Any]:
        """
        Generate the Executive Summary section.
        
        Creates 2-4 short paragraphs covering:
        - Current position
        - Risks
        - Priorities
        - Overall direction
        
        Args:
            bba: BBA model with all report data
            
        Returns:
            Dictionary containing the executive summary
        """
        logger.info(f"[BBA Engine] Generating executive summary for BBA {bba.id}")
        
        context = self._build_context_from_bba(bba)
        
        # Load system prompt
        try:
            system_prompt = load_bba_prompt("bba_system_prompt")
        except FileNotFoundError as e:
            logger.error(f"[BBA Engine] Failed to load prompts: {e}")
            raise
        
        # Build report context
        report_data = {
            "expanded_findings": bba.expanded_findings,
            "snapshot_table": bba.snapshot_table,
            "twelve_month_plan": bba.twelve_month_plan,
        }
        
        user_content = f"""
Generate an Executive Summary for the diagnostic report.

## Client Context
- Client Name: {context['client_name']}
- Industry: {context['industry']}
- Strategic Priorities: {context['strategic_priorities']}

## Report Data
{json.dumps(report_data, separators=(',', ':'))}

Write 2-4 short paragraphs covering:
1. Current position
2. Key risks identified
3. Priorities
4. Overall strategic direction

Return your response as a JSON object with an "executive_summary" key containing the text.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            result = await self.openai_service.generate_json_completion(
                messages=messages,
                reasoning_effort="low",
                max_output_tokens=8192,
            )

            logger.info(f"[BBA Engine] Executive summary generated successfully")
            
            return {
                "executive_summary": result.get("parsed_content", {}).get("executive_summary", ""),
                "tokens_used": result.get("tokens_used", 0),
                "model": result.get("model", "")
            }
            
        except Exception as e:
            logger.error(f"[BBA Engine] Failed to generate executive summary: {e}", exc_info=True)
            raise

    async def extract_context_capture_from_diagnostic_text(
        self,
        diagnostic_text: str,
        file_mappings: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Use LLM to extract context-capture (questionnaire) fields from diagnostic report text
        and/or uploaded files.
        Returns a dict with camelCase keys; only keys for which a value was extracted are present.
        """
        has_text = diagnostic_text and diagnostic_text.strip()
        has_files = bool(file_mappings)
        if not has_text and not has_files:
            return {}
        try:
            prompt = load_bba_prompt("extract_context_capture")
        except FileNotFoundError:
            logger.warning("[BBA Engine] extract_context_capture prompt not found, using inline prompt")
            prompt = (
                "Extract context-capture form fields from the diagnostic report and/or uploaded documents. "
                "Return JSON only with camelCase keys. ALL 9 keys must appear in the output — infer or default any field not explicitly stated: "
                "clientName (string), industry (string), "
                "companySize (one of: startup, small, medium, large, enterprise — default 'small' if unclear), "
                "locations (string — 'Not specified' if absent), "
                "exclusions (string — 'None identified' if absent), "
                "constraints (string — 'None identified' if absent), "
                "preferredRanking (string — 'By business impact and urgency' if not stated), "
                "strategicPriorities (string — synthesise from document goals/challenges), "
                "excludeSaleReadiness (boolean — false unless explicitly excluded)."
            )

        # Build user message content
        user_parts = []
        if has_text:
            user_parts.append(f"Diagnostic report:\n\n{diagnostic_text[:30000]}")
        if has_files:
            user_parts.append("Uploaded documents are also attached. Extract any relevant context-capture fields from them as well.")
        user_content = "\n\n".join(user_parts)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ]

        # Attach the uploaded documents whenever any exist — even when diagnostic
        # text is also present. The diagnostic does NOT contain the uploaded file's
        # contents, so the files must be sent for the model to extract from them.
        pdf_file_ids = None
        tools = None
        if file_mappings:
            pdf_ids, ci_ids = self._separate_files_by_type(file_mappings)
            pdf_file_ids = pdf_ids if pdf_ids else None
            if ci_ids:
                tools = [{
                    "type": "code_interpreter",
                    "container": {
                        "type": "auto",
                        "file_ids": ci_ids
                    }
                }]
            logger.info(f"[BBA Engine] Context capture file categorization: {len(pdf_ids)} PDF(s), {len(ci_ids)} CI file(s)")

        result = await self.openai_service.generate_json_completion(
            messages=messages,
            file_ids=pdf_file_ids,
            tools=tools,
            temperature=0.2,
            max_output_tokens=4096,
        )
        parsed = result.get("parsed_content") or {}
        if not isinstance(parsed, dict):
            return {}

        # Normalize companySize to the BBA enum so the frontend Select can render it.
        # Maps variants like "Small", "small (11-50 employees)", "Medium-sized" -> the enum value.
        if isinstance(parsed.get("companySize"), str):
            raw = parsed["companySize"].strip().lower()
            valid_sizes = ("startup", "small", "medium", "large", "enterprise")
            matched = next((s for s in valid_sizes if raw == s or raw.startswith(s)), None)
            if not matched:
                words = re.findall(r"[a-z]+", raw)
                matched = next((s for s in valid_sizes if s in words), None)
            parsed["companySize"] = matched  # None when unmappable -> dropped by has_value below

        # Filter to known questionnaire keys; omit None and empty strings
        known = {
            "clientName", "industry", "companySize", "locations",
            "exclusions", "constraints", "preferredRanking", "strategicPriorities", "excludeSaleReadiness"
        }
        def has_value(v: Any) -> bool:
            if v is None:
                return False
            if isinstance(v, str) and not v.strip():
                return False
            return True
        return {k: v for k, v in parsed.items() if k in known and has_value(v)}


# Singleton instance
bba_conversation_engine = BBAConversationEngine()


def get_bba_conversation_engine() -> BBAConversationEngine:
    """Get the BBA conversation engine instance."""
    return bba_conversation_engine
