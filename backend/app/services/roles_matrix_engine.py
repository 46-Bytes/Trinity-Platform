"""
Roles & Responsibilities Matrix Engine
Orchestrates the Claude calls that extract responsibilities from the advisor's
inputs and build the matrix rows.
"""
from typing import Dict, Any, List, Optional, Tuple
import json
import logging
from pathlib import Path

from app.services.claude_service import ClaudeService
from app.models.roles_matrix import RolesMatrix

logger = logging.getLogger(__name__)


def load_roles_matrix_prompt(prompt_name: str) -> str:
    """
    Load a roles matrix prompt template from the prompts directory.

    Args:
        prompt_name: Name of the prompt file (without .md extension)

    Returns:
        Prompt content as string
    """
    prompt_path = (
        Path(__file__).resolve().parents[2] / "files" / "prompts" / "roles-matrix" / f"{prompt_name}.md"
    )

    if not prompt_path.exists():
        logger.error(f"Prompt file not found: {prompt_path}")
        raise FileNotFoundError(f"Prompt file not found: {prompt_name}.md")

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


class RolesMatrixEngine:
    """Manages the AI steps of the Roles & Responsibilities Matrix workflow."""

    def __init__(self):
        self.claude_service = ClaudeService()

    # ==================== Context helpers ====================

    def _build_context(self, matrix: RolesMatrix) -> Dict[str, Any]:
        """Build the prompt context from the matrix record."""
        return {
            "staff": matrix.staff or [],
            "included_roles": matrix.included_roles or [],
            "pasted_notes": matrix.pasted_notes or "",
            "file_mappings": matrix.file_mappings or {},
        }

    def _separate_files_by_type(self, file_mappings: Dict[str, str]) -> Tuple[List[str], List[str]]:
        """
        Split file IDs by how they must reach the model.

        PDFs attach directly as document blocks; spreadsheets, Word documents and
        plain text go through the Code Interpreter container.
        """
        # Position descriptions arrive as Word documents as often as PDFs, so
        # doc/docx are routed explicitly rather than falling through as unknown.
        pdf_ext = {"pdf"}
        ci_ext = {
            "csv", "txt", "text", "md", "markdown", "json", "xml", "yaml", "yml",
            "xlsx", "xls", "doc", "docx",
        }

        pdf_file_ids: List[str] = []
        ci_file_ids: List[str] = []

        for filename, file_id in file_mappings.items():
            if not file_id:
                continue

            ext = Path(filename).suffix.lower().lstrip('.')

            if ext in pdf_ext:
                pdf_file_ids.append(file_id)
            elif ext in ci_ext:
                ci_file_ids.append(file_id)
            else:
                logger.warning(
                    f"[Roles Matrix] Unknown file extension '{ext}' for {filename}, "
                    f"treating as Code Interpreter file"
                )
                ci_file_ids.append(file_id)

        return pdf_file_ids, ci_file_ids

    @staticmethod
    def _format_staff(staff: List[Dict[str, Any]]) -> str:
        """Render the staff list as readable lines for the prompt."""
        if not staff:
            return "None supplied"
        lines = []
        for member in staff:
            name = (member or {}).get("name") or "Unnamed"
            role_title = (member or {}).get("role_title")
            lines.append(f"- {name}" + (f" — {role_title}" if role_title else ""))
        return "\n".join(lines)

    def _build_tools(self, ci_file_ids: List[str]) -> Optional[List[Dict[str, Any]]]:
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

    # ==================== Step 2: Extract ====================

    async def extract_responsibilities(
        self,
        matrix: RolesMatrix,
        custom_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract per-person responsibilities from the uploaded documents and notes.

        Returns:
            Dictionary with extracted data, token count and model used.
        """
        logger.info(f"[Roles Matrix] Extracting responsibilities for matrix {matrix.id}")

        context = self._build_context(matrix)

        system_prompt = load_roles_matrix_prompt("system_prompt")
        step_prompt = load_roles_matrix_prompt("extract_responsibilities")

        system_blocks = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": step_prompt, "cache_control": {"type": "ephemeral"}},
        ]

        notes_section = (
            f"## Pasted Responsibilities / Org Chart / Notes\n{context['pasted_notes']}"
            if context['pasted_notes']
            else "## Pasted Responsibilities / Org Chart / Notes\nNone supplied"
        )

        user_content = f"""
Extract the responsibilities for each person from the material below.

## Key Staff
{self._format_staff(context['staff'])}

## Roles Confirmed for the Matrix
{', '.join(context['included_roles']) if context['included_roles'] else 'All staff listed above'}

{notes_section}

## Uploaded Files
{json.dumps(context['file_mappings'], separators=(',', ':'))}

{f"## Additional Instructions from Advisor{chr(10)}{custom_instructions}" if custom_instructions else ""}

Return your response as a JSON object.
"""

        messages = [{"role": "user", "content": user_content}]

        pdf_file_ids, ci_file_ids = self._separate_files_by_type(context['file_mappings'])
        logger.info(
            f"[Roles Matrix] File categorisation: {len(pdf_file_ids)} PDF(s), "
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

            logger.info(f"[Roles Matrix] Responsibilities extracted for matrix {matrix.id}")

            return {
                "extracted": result.get("parsed_content", {}) or {},
                "tokens_used": result.get("tokens_used", 0),
                "model": result.get("model", ""),
            }

        except Exception as e:
            logger.error(
                f"[Roles Matrix] Failed to extract responsibilities: {e}", exc_info=True
            )
            raise

    # ==================== Step 3: Build matrix ====================

    async def build_matrix(
        self,
        matrix: RolesMatrix,
        custom_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build matrix rows from the extracted responsibilities.

        Returns:
            Dictionary with matrix rows, token count and model used.
        """
        logger.info(f"[Roles Matrix] Building matrix rows for matrix {matrix.id}")

        extracted = matrix.extracted_responsibilities
        if not extracted:
            raise ValueError("No extracted responsibilities available to build the matrix")

        context = self._build_context(matrix)

        system_prompt = load_roles_matrix_prompt("system_prompt")
        step_prompt = load_roles_matrix_prompt("build_matrix")

        system_blocks = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": step_prompt, "cache_control": {"type": "ephemeral"}},
        ]

        user_content = f"""
Build the matrix rows from the extracted responsibilities below.

## Roles Confirmed for the Matrix (use this order)
{', '.join(context['included_roles']) if context['included_roles'] else 'Use the order of the people below'}

## Extracted Responsibilities
{json.dumps(extracted, separators=(',', ':'))}

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
            rows = parsed.get("matrix_rows", []) if isinstance(parsed, dict) else []

            logger.info(f"[Roles Matrix] Built {len(rows)} matrix row(s) for matrix {matrix.id}")

            return {
                "matrix_rows": rows,
                "tokens_used": result.get("tokens_used", 0),
                "model": result.get("model", ""),
            }

        except Exception as e:
            logger.error(f"[Roles Matrix] Failed to build matrix: {e}", exc_info=True)
            raise


# Singleton accessor
_engine: Optional[RolesMatrixEngine] = None


def get_roles_matrix_engine() -> RolesMatrixEngine:
    """Get the shared roles matrix engine instance"""
    global _engine
    if _engine is None:
        _engine = RolesMatrixEngine()
    return _engine
