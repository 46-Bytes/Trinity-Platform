"""
Strategic Business Plan Conversation Engine Service
Manages AI-driven cross-analysis, section drafting, revision, and theme surfacing.
Uses ClaudeService.generate_json_completion() with file attachments (matching BBA pattern).
"""
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.claude_service import ClaudeService
from app.models.strategic_business_plan import StrategicBusinessPlan
from app.services.sbp_service import get_sbp_service

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "files" / "prompts" / "strategic-business-plan"


def load_sbp_prompt(prompt_name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = PROMPTS_DIR / f"{prompt_name}.md"
    if not prompt_path.exists():
        logger.error(f"Prompt file not found: {prompt_path}")
        raise FileNotFoundError(f"Prompt file not found: {prompt_name}.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


class SBPConversationEngine:
    """
    Manages the Strategic Business Plan generation workflow.
    Files are attached to Claude API calls as document blocks (PDFs) or
    container_upload blocks with code execution (CSV/XLSX/TXT).
    """

    def __init__(self, db: Session):
        self.db = db
        self.claude_service = ClaudeService()
        self.sbp_service = get_sbp_service(db)

    def _get_plan(self, plan_id: UUID) -> StrategicBusinessPlan:
        plan = self.sbp_service.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        return plan

    # ------------------------------------------------------------------
    # File handling (matches BBA engine pattern)
    # ------------------------------------------------------------------

    def _separate_files_by_type(self, file_mappings: Dict[str, str]) -> Tuple[List[str], List[str]]:
        """
        Separate file IDs by type for proper Claude API routing.
        PDFs go as document blocks (Claude reads natively).
        CSV/TXT/XLSX etc. go through Code Interpreter (container_upload).
        """
        pdf_ext = {"pdf"}
        ci_ext = {"csv", "txt", "text", "md", "markdown", "json", "xml", "yaml", "yml", "xlsx", "xls"}

        pdf_file_ids = []
        ci_file_ids = []

        for filename, file_id in file_mappings.items():
            if not file_id:
                continue
            ext = Path(filename).suffix.lower().lstrip(".")
            if ext in pdf_ext:
                pdf_file_ids.append(file_id)
            elif ext in ci_ext:
                ci_file_ids.append(file_id)
            else:
                # DOCX, PPTX, images — send as document blocks (Claude reads natively)
                pdf_file_ids.append(file_id)

        return pdf_file_ids, ci_file_ids

    # ------------------------------------------------------------------
    # Context builders
    # ------------------------------------------------------------------

    def _build_context(self, plan: StrategicBusinessPlan) -> Dict[str, Any]:
        """Build context dict from the plan model for prompt interpolation."""
        ctx = {
            "client_name": plan.client_name or "Unknown Client",
            "industry": plan.industry or "Unknown Industry",
            "planning_horizon": plan.planning_horizon or "3-year",
            "target_audience": plan.target_audience or "Owners and management team",
            "additional_context": plan.additional_context or "",
            "file_ids": plan.file_ids or [],
            "file_mappings": plan.file_mappings or {},
        }
        if plan.diagnostic_context:
            ctx["diagnostic_context"] = json.dumps(plan.diagnostic_context, default=str)
        if plan.cross_analysis:
            ctx["cross_analysis"] = json.dumps(plan.cross_analysis, default=str)
        if plan.cross_analysis_advisor_notes:
            ctx["advisor_notes"] = plan.cross_analysis_advisor_notes
        if plan.emerging_themes:
            ctx["emerging_themes"] = json.dumps(plan.emerging_themes, default=str)
        return ctx

    def _get_file_content_references(self, plan: StrategicBusinessPlan) -> str:
        """Build a text block listing uploaded files (for prompt context)."""
        file_mappings = plan.file_mappings or {}
        lines = []
        for filename, file_id in file_mappings.items():
            lines.append(f"- {filename} (file_id: {file_id})")
        return "\n".join(lines) if lines else "No files uploaded."

    def _get_approved_sections_context(self, plan: StrategicBusinessPlan) -> str:
        """Build context from already-approved sections for continuity."""
        sections = plan.sections or []
        parts = []
        for s in sections:
            if s.get("status") == "approved" and s.get("content"):
                parts.append(f"## {s['title']}\n{s['content']}")
                if s.get("strategic_implications"):
                    parts.append(f"### Strategic Implications\n{s['strategic_implications']}")
        return "\n\n".join(parts) if parts else ""

    # ------------------------------------------------------------------
    # Core Claude call — uses generate_json_completion with file attachments
    # ------------------------------------------------------------------

    async def _call_claude(self, system_prompt: str, user_prompt: str, plan: StrategicBusinessPlan) -> Dict[str, Any]:
        """
        Call Claude via ClaudeService.generate_json_completion() with proper
        file attachments. PDFs attached as document blocks, CSV/XLSX via
        Code Interpreter container_upload blocks.
        """
        file_mappings = plan.file_mappings or {}
        pdf_file_ids, ci_file_ids = self._separate_files_by_type(file_mappings)

        # Build tools for Code Interpreter if CSV/XLSX files exist
        tools = None
        if ci_file_ids:
            tools = [{
                "type": "code_interpreter",
                "container": {
                    "type": "auto",
                    "file_ids": ci_file_ids,
                },
            }]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        has_files = bool(pdf_file_ids or ci_file_ids)

        # Retry loop — files recently uploaded to Claude may need a moment to be ready
        max_attempts = 3 if has_files else 1
        last_error = None

        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    wait = 2 * attempt  # 2s, 4s
                    logger.info(f"[SBP Engine] Retry attempt {attempt + 1}/{max_attempts} after {wait}s wait")
                    await asyncio.sleep(wait)

                result = await self.claude_service.generate_json_completion(
                    messages=messages,
                    file_ids=pdf_file_ids if pdf_file_ids else None,
                    tools=tools,
                )

                # generate_json_completion returns parsed JSON in "parsed_content"
                parsed = result.get("parsed_content")
                if parsed and isinstance(parsed, dict):
                    return parsed

                # Fallback: try parsing the raw content
                raw = result.get("content", "")
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return {"content": raw}

            except Exception as e:
                last_error = e
                error_msg = str(e)
                # Only retry on 500 server errors (file not ready)
                if "500" in error_msg and attempt < max_attempts - 1:
                    logger.warning(f"[SBP Engine] Got 500 error, will retry: {error_msg}")
                    continue
                raise

        raise last_error  # Should not reach here, but just in case

    # ------------------------------------------------------------------
    # Step 2: Cross-Pattern Analysis
    # ------------------------------------------------------------------

    async def perform_cross_analysis(self, plan_id: UUID, custom_instructions: Optional[str] = None) -> Dict[str, Any]:
        plan = self._get_plan(plan_id)
        ctx = self._build_context(plan)

        try:
            system_prompt = load_sbp_prompt("system_prompt")
        except FileNotFoundError:
            system_prompt = self._default_system_prompt()

        try:
            cross_prompt = load_sbp_prompt("cross_analysis")
        except FileNotFoundError:
            cross_prompt = self._default_cross_analysis_prompt()

        file_refs = self._get_file_content_references(plan)

        user_prompt = cross_prompt.format(
            client_name=ctx["client_name"],
            industry=ctx["industry"],
            planning_horizon=ctx["planning_horizon"],
            target_audience=ctx["target_audience"],
            additional_context=ctx.get("additional_context", ""),
            file_references=file_refs,
            diagnostic_context=ctx.get("diagnostic_context", "None provided"),
            custom_instructions=custom_instructions or "None",
        )

        result = await self._call_claude(system_prompt, user_prompt, plan)

        # Ensure expected keys exist
        if "recurring_themes" not in result:
            result = {
                "recurring_themes": [],
                "tensions": [],
                "correlations": [],
                "data_gaps": [],
                "preliminary_observations": [result.get("content", "")],
            }

        self.sbp_service.save_cross_analysis(plan_id, result)
        return result

    # ------------------------------------------------------------------
    # Step 3: Section Drafting
    # ------------------------------------------------------------------

    async def draft_section(self, plan_id: UUID, section_key: str, custom_instructions: Optional[str] = None) -> Dict[str, Any]:
        plan = self._get_plan(plan_id)
        ctx = self._build_context(plan)

        # Mark section as drafting
        self.sbp_service.update_section(plan_id, section_key, {"status": "drafting"})

        try:
            system_prompt = load_sbp_prompt("system_prompt")
        except FileNotFoundError:
            system_prompt = self._default_system_prompt()

        try:
            section_prompt = load_sbp_prompt(f"section_{section_key}")
        except FileNotFoundError:
            section_prompt = self._default_section_prompt(section_key)

        approved_context = self._get_approved_sections_context(plan)
        file_refs = self._get_file_content_references(plan)

        user_prompt = section_prompt.format(
            client_name=ctx["client_name"],
            industry=ctx["industry"],
            planning_horizon=ctx["planning_horizon"],
            target_audience=ctx["target_audience"],
            additional_context=ctx.get("additional_context", ""),
            cross_analysis=ctx.get("cross_analysis", "Not yet performed"),
            advisor_notes=ctx.get("advisor_notes", "None"),
            emerging_themes=ctx.get("emerging_themes", "Not yet surfaced"),
            approved_sections=approved_context or "None approved yet",
            file_references=file_refs,
            diagnostic_context=ctx.get("diagnostic_context", "None provided"),
            custom_instructions=custom_instructions or "None",
        )

        parsed = await self._call_claude(system_prompt, user_prompt, plan)

        content = parsed.get("content", "")
        implications = parsed.get("strategic_implications", None)

        # Find existing section and preserve history
        # Re-fetch plan to get latest sections after the status update
        plan = self._get_plan(plan_id)
        sections = list(plan.sections or [])
        section_data = next((s for s in sections if s["key"] == section_key), None)
        revision_history = section_data.get("revision_history", []) if section_data else []
        if section_data and section_data.get("content"):
            revision_history.append({
                "content": section_data["content"],
                "strategic_implications": section_data.get("strategic_implications"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        updates = {
            "status": "drafted",
            "content": content,
            "strategic_implications": implications,
            "revision_history": revision_history,
            "draft_count": (section_data.get("draft_count", 0) if section_data else 0) + 1,
        }
        self.sbp_service.update_section(plan_id, section_key, updates)

        return {**updates, "key": section_key, "title": section_data["title"] if section_data else section_key}

    async def revise_section(self, plan_id: UUID, section_key: str, revision_notes: str) -> Dict[str, Any]:
        plan = self._get_plan(plan_id)

        # Mark as revision requested
        self.sbp_service.update_section(plan_id, section_key, {
            "status": "revision_requested",
            "revision_notes": revision_notes,
        })

        # Re-fetch after update
        plan = self._get_plan(plan_id)
        sections = list(plan.sections or [])
        section_data = next((s for s in sections if s["key"] == section_key), None)
        current_content = section_data.get("content", "") if section_data else ""

        try:
            system_prompt = load_sbp_prompt("system_prompt")
        except FileNotFoundError:
            system_prompt = self._default_system_prompt()

        try:
            revision_prompt = load_sbp_prompt("revision")
        except FileNotFoundError:
            revision_prompt = self._default_revision_prompt()

        ctx = self._build_context(plan)

        user_prompt = revision_prompt.format(
            section_title=section_data["title"] if section_data else section_key,
            current_content=current_content,
            revision_notes=revision_notes,
            client_name=ctx["client_name"],
            industry=ctx["industry"],
            planning_horizon=ctx["planning_horizon"],
        )

        parsed = await self._call_claude(system_prompt, user_prompt, plan)

        content = parsed.get("content", "")
        implications = parsed.get("strategic_implications", None)

        revision_history = section_data.get("revision_history", []) if section_data else []
        if current_content:
            revision_history.append({
                "content": current_content,
                "strategic_implications": section_data.get("strategic_implications") if section_data else None,
                "revision_notes": revision_notes,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        updates = {
            "status": "drafted",
            "content": content,
            "strategic_implications": implications,
            "revision_notes": None,
            "revision_history": revision_history,
            "draft_count": (section_data.get("draft_count", 0) if section_data else 0) + 1,
        }
        self.sbp_service.update_section(plan_id, section_key, updates)

        return {**updates, "key": section_key, "title": section_data["title"] if section_data else section_key}

    # ------------------------------------------------------------------
    # Emerging Themes
    # ------------------------------------------------------------------

    async def surface_emerging_themes(self, plan_id: UUID) -> Dict[str, Any]:
        plan = self._get_plan(plan_id)
        ctx = self._build_context(plan)
        approved_context = self._get_approved_sections_context(plan)

        try:
            system_prompt = load_sbp_prompt("system_prompt")
        except FileNotFoundError:
            system_prompt = self._default_system_prompt()

        try:
            themes_prompt = load_sbp_prompt("emerging_themes")
        except FileNotFoundError:
            themes_prompt = self._default_emerging_themes_prompt()

        user_prompt = themes_prompt.format(
            client_name=ctx["client_name"],
            industry=ctx["industry"],
            approved_sections=approved_context or "No sections approved yet",
            cross_analysis=ctx.get("cross_analysis", "Not available"),
        )

        parsed = await self._call_claude(system_prompt, user_prompt, plan)

        if "themes" not in parsed:
            parsed = {"themes": [], "summary": parsed.get("content", "")}

        self.sbp_service.save_emerging_themes(plan_id, parsed)
        return parsed

    # ------------------------------------------------------------------
    # Default Prompts (fallbacks if prompt files don't exist yet)
    # ------------------------------------------------------------------

    def _default_system_prompt(self) -> str:
        return """You are the Trinity Strategic Business Plan Assistant.
Your role is to help create professional Strategic Business Plans for SME clients.
You produce work to a standard comparable with senior management consulting firms.
Use British English. Only use bold for headings and table headings.
All content must come from the provided source materials — do not invent facts, figures, or strategic intent.
Return responses as JSON when instructed."""

    def _default_cross_analysis_prompt(self) -> str:
        return """Perform a cross-pattern analysis across all provided materials for {client_name} ({industry}).

Planning horizon: {planning_horizon}
Target audience: {target_audience}
Additional context: {additional_context}

Uploaded files:
{file_references}

Diagnostic context:
{diagnostic_context}

Custom instructions: {custom_instructions}

Analyse all materials and return a JSON object with:
{{
  "recurring_themes": [{{ "theme": "...", "description": "...", "sources": [...], "signal_strength": "very_strong|strong|moderate" }}],
  "tensions": [{{ "tension": "...", "description": "..." }}],
  "correlations": [{{ "correlation": "...", "description": "..." }}],
  "data_gaps": ["..."],
  "preliminary_observations": ["..."]
}}

Identify recurring themes, tensions/contradictions, correlations between issues, and any data gaps.
Focus on strategic signals, not commentary."""

    def _default_section_prompt(self, section_key: str) -> str:
        return """Draft the "{section_key}" section of the Strategic Business Plan for {{client_name}} ({{industry}}).

Planning horizon: {{planning_horizon}}
Target audience: {{target_audience}}
Additional context: {{additional_context}}

Cross-analysis results:
{{cross_analysis}}

Advisor notes: {{advisor_notes}}
Emerging themes: {{emerging_themes}}

Previously approved sections:
{{approved_sections}}

Uploaded files:
{{file_references}}

Diagnostic context:
{{diagnostic_context}}

Custom instructions: {{custom_instructions}}

Return a JSON object with:
{{{{
  "content": "<HTML content for this section>",
  "strategic_implications": "<HTML content for strategic implications, if applicable, otherwise null>"
}}}}

Draft professionally. Content must come only from the provided source materials.
Use tables where comparison or prioritisation exists.
Use British English. Only bold headings.""".format(section_key=section_key)

    def _default_revision_prompt(self) -> str:
        return """Revise the following section of the Strategic Business Plan for {client_name} ({industry}).

Section: {section_title}

Current content:
{current_content}

Advisor's revision notes:
{revision_notes}

Planning horizon: {planning_horizon}

Apply the requested changes while maintaining consistency with the rest of the plan.
Return a JSON object with:
{{
  "content": "<revised HTML content>",
  "strategic_implications": "<revised strategic implications HTML, or null>"
}}"""

    def _default_emerging_themes_prompt(self) -> str:
        return """Based on the approved sections so far for {client_name} ({industry}), surface emerging strategic themes.

Cross-analysis results:
{cross_analysis}

Approved sections:
{approved_sections}

Return a JSON object with:
{{
  "themes": [{{ "theme": "...", "description": "...", "supporting_sections": [...], "signal_strength": "very_strong|strong|moderate" }}],
  "summary": "Plain language summary of integrated themes"
}}

Identify which implications are repeating, which signals appear strongest, and which are weakest."""


def get_sbp_conversation_engine(db: Session) -> SBPConversationEngine:
    """Factory function for dependency injection."""
    return SBPConversationEngine(db)
