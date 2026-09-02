"""
PD & Role Scorecard Engine
Orchestrates the Claude calls that parse the roles matrix and generate the
Position Description and Half-Yearly Role Scorecard for one role at a time.
"""
from typing import Dict, Any, List, Optional, Tuple
import json
import logging
from pathlib import Path

from app.services.claude_service import ClaudeService
from app.models.pd_scorecard import PDScorecard, PDScorecardRole
from app.services.pd_scorecard_service import rows_for_role

logger = logging.getLogger(__name__)


def load_pd_scorecard_prompt(prompt_name: str) -> str:
    """
    Load a PD scorecard prompt template from the prompts directory.

    Args:
        prompt_name: Name of the prompt file (without .md extension)

    Returns:
        Prompt content as string
    """
    prompt_path = (
        Path(__file__).resolve().parents[2] / "files" / "prompts" / "pd-scorecard" / f"{prompt_name}.md"
    )

    if not prompt_path.exists():
        logger.error(f"Prompt file not found: {prompt_path}")
        raise FileNotFoundError(f"Prompt file not found: {prompt_name}.md")

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


class PDScorecardEngine:
    """Manages the AI steps of the PD & Role Scorecard workflow."""

    def __init__(self):
        self.claude_service = ClaudeService()

    # ==================== Context helpers ====================

    @staticmethod
    def _separate_files_by_type(
        file_mappings: Dict[str, str]
    ) -> Tuple[List[str], List[str]]:
        """
        Split file IDs by how they must reach the model.

        PDFs attach directly as document blocks; spreadsheets, Word documents and
        plain text go through the Code Interpreter container. The roles matrix
        normally arrives as .xlsx and reference PDs as .docx, so both are routed
        explicitly rather than falling through as unknown.
        """
        pdf_ext = {"pdf"}
        ci_ext = {
            "csv", "txt", "text", "md", "markdown", "json", "xml", "yaml", "yml",
            "xlsx", "xls", "doc", "docx",
        }

        pdf_file_ids: List[str] = []
        ci_file_ids: List[str] = []

        for filename, file_id in (file_mappings or {}).items():
            if not file_id:
                continue

            ext = Path(filename).suffix.lower().lstrip('.')

            if ext in pdf_ext:
                pdf_file_ids.append(file_id)
            elif ext in ci_ext:
                ci_file_ids.append(file_id)
            else:
                logger.warning(
                    f"[PD Scorecard] Unknown file extension '{ext}' for {filename}, "
                    f"treating as Code Interpreter file"
                )
                ci_file_ids.append(file_id)

        return pdf_file_ids, ci_file_ids

    @staticmethod
    def _build_tools(ci_file_ids: List[str]) -> Optional[List[Dict[str, Any]]]:
        """Build the Code Interpreter tool block when non-PDF files are attached."""
        if not ci_file_ids:
            return None
        return [{
            "type": "code_interpreter",
            "container": {
                "type": "auto",
                "file_ids": ci_file_ids,
            },
        }]

    @staticmethod
    def _reference_pd_note(build: PDScorecard) -> str:
        """Name the reference PDs and restate that they inform tone only."""
        references = build.reference_pd_files or []
        if not references:
            return "## Reference Position Descriptions\nNone supplied"
        return (
            "## Reference Position Descriptions (tone, wording and structure only)\n"
            + "\n".join(f"- {name}" for name in references)
            + "\nNever carry a responsibility forward from these. All responsibilities "
              "come from the matrix."
        )

    @staticmethod
    def _role_context(build: PDScorecard, role: PDScorecardRole) -> str:
        """Render the role's own matrix rows, grouped by flag."""
        grouped = role.source_responsibilities or rows_for_role(
            build.matrix_rows or [], role.role_title, role.person_name
        )
        return json.dumps(grouped, separators=(',', ':'))

    # ==================== Step 2: Parse the matrix ====================

    async def extract_roles(
        self,
        build: PDScorecard,
        custom_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parse the uploaded Roles & Responsibilities matrix into rows and roles.

        Returns:
            Dictionary with matrix rows, roles, token count and model used.
        """
        logger.info(f"[PD Scorecard] Extracting roles for build {build.id}")

        system_prompt = load_pd_scorecard_prompt("system_prompt")
        step_prompt = load_pd_scorecard_prompt("extract_roles")

        system_blocks = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": step_prompt, "cache_control": {"type": "ephemeral"}},
        ]

        notes_section = (
            f"## Pasted Matrix Content / Notes\n{build.pasted_notes}"
            if build.pasted_notes
            else "## Pasted Matrix Content / Notes\nNone supplied"
        )

        user_content = f"""
Parse the Roles & Responsibilities matrix below into matrix rows and the distinct roles it contains.

## Client
{build.client_name or 'Not supplied'}

{notes_section}

{self._reference_pd_note(build)}

## Uploaded Files
{json.dumps(build.file_mappings or {}, separators=(',', ':'))}

{f"## Additional Instructions from Advisor{chr(10)}{custom_instructions}" if custom_instructions else ""}

Return your response as a JSON object.
"""

        messages = [{"role": "user", "content": user_content}]

        pdf_file_ids, ci_file_ids = self._separate_files_by_type(build.file_mappings or {})
        logger.info(
            f"[PD Scorecard] File categorisation: {len(pdf_file_ids)} PDF(s), "
            f"{len(ci_file_ids)} Code Interpreter file(s)"
        )

        try:
            result = await self.claude_service.generate_json_completion(
                messages=messages,
                system_blocks=system_blocks,
                file_ids=pdf_file_ids if pdf_file_ids else None,
                tools=self._build_tools(ci_file_ids),
                reasoning_effort="medium",
                max_output_tokens=16384,
            )

            parsed = result.get("parsed_content", {}) or {}
            matrix_rows = parsed.get("matrix_rows", []) if isinstance(parsed, dict) else []
            roles = parsed.get("roles", []) if isinstance(parsed, dict) else []

            logger.info(
                f"[PD Scorecard] Parsed {len(matrix_rows)} row(s) and {len(roles)} role(s) "
                f"for build {build.id}"
            )

            return {
                "matrix_rows": matrix_rows,
                "roles": roles,
                "tokens_used": result.get("tokens_used", 0),
                "model": result.get("model", ""),
            }

        except Exception as e:
            logger.error(f"[PD Scorecard] Failed to extract roles: {e}", exc_info=True)
            raise

    # ==================== Step 3: Position Description ====================

    async def generate_pd(
        self,
        build: PDScorecard,
        role: PDScorecardRole,
        custom_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate the Position Description draft for a single role.

        Returns:
            Dictionary with PD content, token count and model used.
        """
        logger.info(f"[PD Scorecard] Generating PD for role {role.id} ({role.role_title})")

        if not build.matrix_rows:
            raise ValueError("Parse the roles matrix before generating a position description")

        system_prompt = load_pd_scorecard_prompt("system_prompt")
        step_prompt = load_pd_scorecard_prompt("generate_pd")

        system_blocks = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": step_prompt, "cache_control": {"type": "ephemeral"}},
        ]

        user_content = f"""
Generate the Position Description for the role below.

## Role
{role.role_title}{f" — currently held by {role.person_name}" if role.person_name else ""}

## Client
{build.client_name or 'Not supplied'}

## Financial Year Range for Transition Focus
{build.fy_range or 'Not supplied — omit financial year references'}

## This Role's Matrix Rows (grouped by retain, gain and lose)
{self._role_context(build, role)}

{self._reference_pd_note(build)}

{f"## Additional Instructions from Advisor{chr(10)}{custom_instructions}" if custom_instructions else ""}

Return your response as a JSON object.
"""

        messages = [{"role": "user", "content": user_content}]

        pdf_file_ids, ci_file_ids = self._separate_files_by_type(build.file_mappings or {})

        try:
            result = await self.claude_service.generate_json_completion(
                messages=messages,
                system_blocks=system_blocks,
                file_ids=pdf_file_ids if pdf_file_ids else None,
                tools=self._build_tools(ci_file_ids),
                reasoning_effort="medium",
                max_output_tokens=16384,
            )

            parsed = result.get("parsed_content", {}) or {}
            pd_content = parsed.get("pd_content", {}) if isinstance(parsed, dict) else {}

            logger.info(f"[PD Scorecard] Generated PD for role {role.id}")

            return {
                "pd_content": pd_content or {},
                "tokens_used": result.get("tokens_used", 0),
                "model": result.get("model", ""),
            }

        except Exception as e:
            logger.error(f"[PD Scorecard] Failed to generate PD: {e}", exc_info=True)
            raise

    # ==================== Step 4: Scorecard ====================

    async def generate_scorecard(
        self,
        build: PDScorecard,
        role: PDScorecardRole,
        custom_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate the Half-Yearly Role Scorecard draft for a single role, aligned
        to its approved Position Description.

        Returns:
            Dictionary with scorecard content, token count and model used.
        """
        logger.info(f"[PD Scorecard] Generating scorecard for role {role.id} ({role.role_title})")

        if not role.pd_content:
            raise ValueError("Generate the position description before the scorecard")

        system_prompt = load_pd_scorecard_prompt("system_prompt")
        step_prompt = load_pd_scorecard_prompt("generate_scorecard")

        system_blocks = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": step_prompt, "cache_control": {"type": "ephemeral"}},
        ]

        user_content = f"""
Generate the Half-Yearly Role Scorecard for the role below, aligned to its approved Position Description.

## Role
{role.role_title}{f" — currently held by {role.person_name}" if role.person_name else ""}

## Client
{build.client_name or 'Not supplied'}

## Financial Year Range for Transition Milestones
{build.fy_range or 'Not supplied — omit financial year references'}

## Approved Position Description
{json.dumps(role.pd_content, separators=(',', ':'))}

## This Role's Matrix Rows (grouped by retain, gain and lose)
{self._role_context(build, role)}

{f"## Additional Instructions from Advisor{chr(10)}{custom_instructions}" if custom_instructions else ""}

Return your response as a JSON object.
"""

        messages = [{"role": "user", "content": user_content}]

        try:
            result = await self.claude_service.generate_json_completion(
                messages=messages,
                system_blocks=system_blocks,
                reasoning_effort="medium",
                max_output_tokens=16384,
            )

            parsed = result.get("parsed_content", {}) or {}
            scorecard_content = (
                parsed.get("scorecard_content", {}) if isinstance(parsed, dict) else {}
            )

            logger.info(f"[PD Scorecard] Generated scorecard for role {role.id}")

            return {
                "scorecard_content": scorecard_content or {},
                "tokens_used": result.get("tokens_used", 0),
                "model": result.get("model", ""),
            }

        except Exception as e:
            logger.error(f"[PD Scorecard] Failed to generate scorecard: {e}", exc_info=True)
            raise


# Singleton accessor
_engine: Optional[PDScorecardEngine] = None


def get_pd_scorecard_engine() -> PDScorecardEngine:
    """Get the shared PD scorecard engine instance"""
    global _engine
    if _engine is None:
        _engine = PDScorecardEngine()
    return _engine
