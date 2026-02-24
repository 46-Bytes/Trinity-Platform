"""
BBA Conversation Engine Service
Manages the BBA diagnostic report generation workflow through Steps 3-7.
"""
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
import json
import logging
from pathlib import Path

from app.services.openai_service import OpenAIService
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
        """Initialize the conversation engine with OpenAI service."""
        self.openai_service = OpenAIService()
    
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
        return ctx
    
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
        
        # Build the full system message
        system_content = f"{system_prompt}\n\n{step_prompt}"
        
        # Build optional prior diagnostic section when BBA was created from a diagnostic
        diagnostic_section = ""
        if context.get("diagnostic_context"):
            dc = context["diagnostic_context"]
            report_html = dc.get("report_html") if isinstance(dc, dict) else None
            ai_analysis = dc.get("ai_analysis") if isinstance(dc, dict) else None
            if report_html:
                diagnostic_section = f"\n\n## Prior Diagnostic Report (use as context)\n{report_html}\n"
            elif ai_analysis:
                advisor_report = ai_analysis.get("advisorReport", "") if isinstance(ai_analysis, dict) else ""
                if advisor_report:
                    diagnostic_section = f"\n\n## Prior Diagnostic Report (use as context)\n{advisor_report}\n"
                else:
                    diagnostic_section = f"\n\n## Prior Diagnostic Analysis (use as context)\n{json.dumps(ai_analysis, indent=2)}\n"

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
{json.dumps(context['file_mappings'], indent=2)}

{f"## Additional Instructions from Advisor{chr(10)}{custom_instructions}" if custom_instructions else ""}

Please analyse all uploaded files and generate a ranked list of Top 10 findings.
Return your response as a JSON object.
"""
        
        messages = [
            {"role": "system", "content": system_content},
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
                file_ids=pdf_file_ids if pdf_file_ids else None,  # Only PDFs as input_file
                tools=tools,  # CSV/TXT/XLSX go to Code Interpreter
                reasoning_effort="medium"
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
        
        system_content = f"{system_prompt}\n\n{step_prompt}"
        
        user_content = f"""
Expand the following draft findings into full paragraphs.

## Client Context
- Client Name: {context['client_name']}
- Industry: {context['industry']}
- Strategic Priorities: {context['strategic_priorities']}

## Draft Findings to Expand
{json.dumps(findings, indent=2)}

For each finding, write 1-3 paragraphs explaining:
1. The issue and its current state
2. The business impact
3. Why it matters for future goals

Return your response as a JSON object.
"""
        
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]
        
        # Separate files by type: PDFs go as input_file, CSV/TXT/XLSX go to Code Interpreter
        file_mappings = context['file_mappings'] or {}
        pdf_file_ids, ci_file_ids = self._separate_files_by_type(file_mappings)
        
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
                file_ids=pdf_file_ids if pdf_file_ids else None,  # Only PDFs as input_file
                tools=tools,  # CSV/TXT/XLSX go to Code Interpreter
                reasoning_effort="medium"
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
        
        system_content = f"{system_prompt}\n\n{step_prompt}"
        
        user_content = f"""
Generate the Key Findings & Recommendations Snapshot table.

## Client Context
- Client Name: {context['client_name']}
- Industry: {context['industry']}

## Expanded Findings
{json.dumps(expanded_findings, indent=2)}

Create a concise three-column table that fits on one Word page.
Return your response as a JSON object.
"""
        
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]
        
        try:
            result = await self.openai_service.generate_json_completion(
                messages=messages,
                reasoning_effort="low"
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
        
        system_content = f"{system_prompt}\n\n{step_prompt}"
        
        user_content = f"""
Generate the 12-Month Recommendations Plan.

## Client Context
- Client Name: {context['client_name']}
- Industry: {context['industry']}
- Strategic Priorities: {context['strategic_priorities']}

## Expanded Findings
{json.dumps(expanded_findings, indent=2)}

## Snapshot Table
{json.dumps(snapshot_table, indent=2) if snapshot_table else "Not yet generated"}

For each finding, create a detailed recommendation with:
- Purpose
- Key Objectives (3-5 bullets)
- Actions to Complete (5-10 points)
- BBA Support Outline
- Expected Outcomes

Also include the "Notes on the 12-Month Recommendations Plan" disclaimer.

Return your response as a JSON object.
"""
        
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]
        
        # Separate files by type: PDFs go as input_file, CSV/TXT/XLSX go to Code Interpreter
        file_mappings = context['file_mappings'] or {}
        pdf_file_ids, ci_file_ids = self._separate_files_by_type(file_mappings)
        
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
                file_ids=pdf_file_ids if pdf_file_ids else None,  # Only PDFs as input_file
                tools=tools,  # CSV/TXT/XLSX go to Code Interpreter
                reasoning_effort="high"
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
        
        system_content = f"{system_prompt}\n\n{step_prompt}"
        
        # Build current report state
        current_report = {
            "draft_findings": bba.draft_findings,
            "expanded_findings": bba.expanded_findings,
            "snapshot_table": bba.snapshot_table,
            "twelve_month_plan": bba.twelve_month_plan,
        }
        
        user_content = f"""
Apply the following edits to the report.

## Client Context
- Client Name: {context['client_name']}
- Industry: {context['industry']}

## Current Report State
{json.dumps(current_report, indent=2)}

## Requested Edits
{json.dumps(edits, indent=2)}

Apply all requested changes while maintaining:
- Consistent formatting
- Section order
- Professional tone
- British English spelling

Return the updated sections as a JSON object.
"""
        
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]
        
        try:
            result = await self.openai_service.generate_json_completion(
                messages=messages,
                reasoning_effort="medium"
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
{json.dumps(report_data, indent=2)}

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
                reasoning_effort="medium"
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

    async def extract_context_capture_from_diagnostic_text(self, diagnostic_text: str) -> Dict[str, Any]:
        """
        Use LLM to extract context-capture (questionnaire) fields from diagnostic report text.
        Returns a dict with camelCase keys; only keys for which a value was extracted are present.
        """
        if not diagnostic_text or not diagnostic_text.strip():
            return {}
        try:
            prompt = load_bba_prompt("extract_context_capture")
        except FileNotFoundError:
            logger.warning("[BBA Engine] extract_context_capture prompt not found, using inline prompt")
            prompt = (
                "Extract context-capture form fields from the diagnostic report. "
                "Return JSON only with camelCase keys. Include only keys you can fill: "
                "clientName, industry, companySize, locations, exclusions, constraints, "
                "preferredRanking, strategicPriorities, excludeSaleReadiness (boolean). "
                "companySize must be one of: startup, small, medium, large, enterprise."
            )
        text_for_llm = diagnostic_text[:30000]  # cap length
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Diagnostic report:\n\n{text_for_llm}"},
        ]
        result = await self.openai_service.generate_json_completion(
            messages=messages,
            temperature=0.2,
        )
        parsed = result.get("parsed_content") or {}
        if not isinstance(parsed, dict):
            return {}
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
