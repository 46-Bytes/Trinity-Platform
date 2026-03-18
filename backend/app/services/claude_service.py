"""
Claude service for Anthropic Claude AI interactions using Messages API.
Mirrors OpenAIService interface exactly for drop-in replacement.
"""
from typing import Dict, Any, List, Optional, Tuple
import json
import os
import time
import logging
import mimetypes

import httpx
from anthropic import AsyncAnthropic
from app.config import settings

logger = logging.getLogger(__name__)


class ClaudeService:
    """Service for interacting with Anthropic Claude Messages API"""

    # Class-level client that will be initialized once at startup
    _client: Optional[AsyncAnthropic] = None

    def __init__(self):
        """Initialize Claude service (client is initialized separately at startup)"""
        self.temperature = settings.ANTHROPIC_TEMPERATURE

    @classmethod
    def initialize_client(cls):
        """Initialize the Anthropic client once at application startup"""
        if cls._client is None:
            timeout_seconds = settings.ANTHROPIC_TIMEOUT or 600.0
            cls._client = AsyncAnthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=timeout_seconds,
                    write=10.0,
                    pool=10.0,
                ),
                max_retries=2,
            )
            timeout_str = f"{timeout_seconds} seconds ({timeout_seconds / 60:.1f} minutes)"
            logger.info(f"Claude client initialized with timeout: {timeout_str}")
        return cls._client

    @property
    def client(self) -> AsyncAnthropic:
        """Get the shared Anthropic client instance"""
        if ClaudeService._client is None:
            raise RuntimeError(
                "Claude client not initialized. Call ClaudeService.initialize_client() "
                "at application startup (e.g., in main.py startup event)."
            )
        return ClaudeService._client

    # ==================== MESSAGE CONVERSION ====================

    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type from filename"""
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            return mime_type
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".csv": "text/csv",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".txt": "text/plain",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".json": "application/json",
            ".md": "text/plain",
            ".rtf": "application/rtf",
        }
        return mime_map.get(ext, "application/octet-stream")

    def _is_image_file_id(self, file_id: str) -> bool:
        """
        Heuristic to determine if a file_id refers to an image.
        In practice, callers should provide file metadata. This is a fallback.
        """
        # Claude file IDs don't encode type, so we default to document
        return False

    def _convert_messages_to_claude_format(
        self,
        messages: List[Dict[str, str]],
        file_ids: Optional[List[str]] = None,
        ci_file_ids: Optional[List[str]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Convert chat messages to Claude Messages API format.

        Key differences from OpenAI:
        - System messages extracted to separate 'system' parameter
        - File attachments use 'document'/'image'/'container_upload' blocks

        Args:
            messages: List of message objects with 'role' and 'content'
            file_ids: Optional list of file IDs to attach as document blocks (PDFs, text)
            ci_file_ids: Optional list of file IDs for code execution (CSV, XLSX) as container_upload blocks

        Returns:
            Tuple of (system_prompt, claude_messages)
        """
        system_parts: List[str] = []
        claude_messages: List[Dict[str, Any]] = []

        for idx, msg in enumerate(messages):
            role = msg["role"]
            content = msg["content"]

            # Extract system/developer messages into system prompt
            if role in ("system", "developer"):
                system_parts.append(content)
                continue

            # Check if this is the last user message (for file attachments)
            is_last_user_message = (
                role == "user"
                and idx == len(messages) - 1
                and (file_ids or ci_file_ids)
            )

            if is_last_user_message:
                # Build content array with files and text
                content_array: List[Dict[str, Any]] = []

                # Add PDF/text files as document blocks
                if file_ids:
                    for fid in file_ids:
                        content_array.append({
                            "type": "document",
                            "source": {
                                "type": "file",
                                "file_id": fid,
                            },
                        })

                # Add CSV/XLSX files as container_upload blocks (for code execution tool)
                if ci_file_ids:
                    for fid in ci_file_ids:
                        content_array.append({
                            "type": "container_upload",
                            "file_id": fid,
                        })

                # Add text content
                content_array.append({
                    "type": "text",
                    "text": content,
                })

                claude_messages.append({
                    "role": role,
                    "content": content_array,
                })
            else:
                # Regular message without files
                claude_messages.append({
                    "role": role,
                    "content": content,
                })

        system_prompt = "\n\n".join(system_parts) if system_parts else ""
        return system_prompt, claude_messages

    # ==================== CORE COMPLETION ====================

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        json_mode: bool = False,
        reasoning_effort: Optional[str] = None,
        file_ids: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate completion from Claude using Messages API.

        Maintains the same interface as OpenAIService.generate_completion().

        Args:
            messages: List of message objects with 'role' and 'content'
                     ('system'/'developer' role extracted to system param)
            temperature: Override default temperature
            json_mode: Enable structured JSON output
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            file_ids: Optional list of Claude file IDs to attach to the last user message
            tools: Optional list of tools (code_interpreter mapped to code_execution)
            model: Model to use for the response
            max_output_tokens: Max tokens for the response
        Returns:
            Dictionary containing response and metadata (same shape as OpenAI service)
        """
        try:
            use_model = model or settings.ANTHROPIC_MODEL
            logger.info(f"Claude Model: {use_model}")

            # Separate code_interpreter/code_execution file IDs from document file IDs
            ci_file_ids: List[str] = []
            claude_tools: Optional[List[Dict[str, Any]]] = None

            if tools:
                for t in tools:
                    if not isinstance(t, dict):
                        continue
                    tool_type = t.get("type", "")
                    # Map OpenAI code_interpreter to Claude code_execution
                    if tool_type == "code_interpreter":
                        claude_tools = claude_tools or []
                        claude_tools.append({
                            "type": "code_execution_20250825",
                            "name": "code_execution",
                        })
                        # Extract file_ids from container config
                        container = t.get("container", {})
                        container_file_ids = container.get("file_ids", [])
                        ci_file_ids.extend(container_file_ids)
                    elif tool_type == "code_execution_20250825":
                        # Already in Claude format
                        claude_tools = claude_tools or []
                        claude_tools.append(t)
                    else:
                        # Pass through other tool types
                        claude_tools = claude_tools or []
                        claude_tools.append(t)

            # Convert messages to Claude format
            system_prompt, claude_messages = self._convert_messages_to_claude_format(
                messages,
                file_ids=file_ids,
                ci_file_ids=ci_file_ids if ci_file_ids else None,
            )

            # If json_mode, append instruction to system prompt for JSON enforcement
            if json_mode:
                json_instruction = (
                    "\n\nIMPORTANT: You MUST respond with valid JSON only. "
                    "No markdown fences, no explanations, no text outside the JSON object."
                )
                system_prompt = (system_prompt + json_instruction) if system_prompt else json_instruction.strip()

            # Prepare parameters
            max_tokens = max_output_tokens or settings.ANTHROPIC_MAX_TOKENS
            temp = temperature if temperature is not None else self.temperature

            params: Dict[str, Any] = {
                "model": use_model,
                "max_tokens": max_tokens,
                "messages": claude_messages,
                "betas": ["files-api-2025-04-14"],
            }

            if system_prompt:
                params["system"] = system_prompt

            # Handle reasoning effort → extended thinking
            if reasoning_effort and reasoning_effort.lower() in ("medium", "high"):
                budget_map = {"medium": 10000, "high": 32000}
                budget = budget_map.get(reasoning_effort.lower(), 10000)
                params["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": budget,
                }
                # Claude requires temperature=1.0 when thinking is enabled
                params["temperature"] = 1.0
            else:
                # Only set temperature when thinking is NOT enabled
                params["temperature"] = temp

            if claude_tools:
                params["tools"] = claude_tools

            start_time = time.time()
            try:
                logger.info("[Claude API] Making API call to Claude Messages API...")
                response = await self.client.beta.messages.create(**params)

                elapsed_time = time.time() - start_time
                logger.info(f"[Claude API] API call succeeded in {elapsed_time:.2f} seconds")

            except Exception as executor_error:
                elapsed_time = time.time() - start_time
                error_msg = str(executor_error)
                error_type = type(executor_error).__name__

                logger.error(f"[Claude API] API call failed after {elapsed_time:.2f} seconds")
                logger.error(f"[Claude API] Error type: {error_type}")
                logger.error(f"[Claude API] Error message: {error_msg}")

                if elapsed_time >= 600:
                    logger.error(f"[Claude API] Request took {elapsed_time:.2f} seconds - likely a timeout")

                # Check for HTTP status codes
                status_code = getattr(executor_error, "status_code", None)
                if status_code:
                    logger.error(f"[Claude API] HTTP Status Code: {status_code}")
                    if status_code == 529:
                        logger.error("[Claude API] API overloaded (529). SDK will retry automatically.")
                    elif status_code == 429:
                        logger.error("[Claude API] Rate limit exceeded (429). SDK will retry automatically.")
                    elif status_code >= 500:
                        logger.error(f"[Claude API] Server error ({status_code}). SDK will retry automatically.")

                logger.error("[Claude API] Full exception details:", exc_info=True)
                raise

            # Extract text content from response (skip thinking blocks)
            content = ""
            for block in response.content:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    content = getattr(block, "text", "")
                    break

            # Fallback: try to get any text from content blocks
            if not content:
                for block in response.content:
                    block_type = getattr(block, "type", None)
                    if block_type == "text":
                        text = getattr(block, "text", "")
                        if text:
                            content = text
                            break

            # Extract content from code execution results if present
            if not content:
                ci_chunks: List[str] = []
                for block in response.content:
                    block_type = getattr(block, "type", None)
                    if block_type == "bash_code_execution_tool_result":
                        result_content = getattr(block, "content", None)
                        if result_content:
                            result_type = getattr(result_content, "type", None)
                            if result_type == "bash_code_execution_result":
                                for item in getattr(result_content, "content", []):
                                    text = getattr(item, "text", None)
                                    if text:
                                        ci_chunks.append(str(text))
                if ci_chunks:
                    content = "\n".join(ci_chunks).strip()
                    logger.info(f"[Claude API] Recovered content from code execution results ({len(ci_chunks)} chunks)")

            # Extract token usage
            input_tokens = getattr(response.usage, "input_tokens", 0) if hasattr(response, "usage") else 0
            output_tokens = getattr(response.usage, "output_tokens", 0) if hasattr(response, "usage") else 0
            tokens_used = input_tokens + output_tokens
            stop_reason = getattr(response, "stop_reason", "end_turn")

            logger.info(f"[Claude API] Token usage - Total: {tokens_used}, Input: {input_tokens}, Output: {output_tokens}")
            logger.info(f"[Claude API] Stop reason: {stop_reason}")

            if not content:
                logger.warning(
                    "[Claude API] Empty content returned. "
                    "stop_reason=%s tokens_used=%s response_id=%s",
                    stop_reason,
                    tokens_used,
                    getattr(response, "id", None),
                )

            # Return structured response (same shape as OpenAI service)
            return {
                "content": content,
                "model": use_model,
                "tokens_used": tokens_used,
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "finish_reason": stop_reason,
                "response_id": getattr(response, "id", None),
                "output_summary": [],
            }

        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__

            logger.error(f"[Claude API] API call failed after all retries")
            logger.error(f"[Claude API] Final error type: {error_type}")
            logger.error(f"[Claude API] Final error message: {error_msg}")
            logger.error("[Claude API] Full exception traceback:", exc_info=True)

            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                logger.error(f"[Claude API] Timeout error detected. Timeout setting: {settings.ANTHROPIC_TIMEOUT} seconds")
                raise Exception(
                    f"Claude API request timed out after {settings.ANTHROPIC_TIMEOUT} seconds. "
                    f"Error: {error_msg}"
                )

            if "api key" in error_msg.lower() or "authentication" in error_msg.lower():
                logger.error("[Claude API] Authentication error detected")
                raise Exception(
                    f"Claude API authentication failed. Please check your ANTHROPIC_API_KEY. "
                    f"Error: {error_msg}"
                )

            if "overloaded" in error_msg.lower() or "529" in error_msg:
                logger.error("[Claude API] API overloaded after all retries")
                raise Exception(
                    f"Claude API is overloaded after all retries. Please try again later. "
                    f"Error: {error_msg}"
                )

            if "429" in error_msg or "rate limit" in error_msg.lower():
                logger.error("[Claude API] Rate limit error after all retries")
                raise Exception(
                    f"Claude API rate limit exceeded after all retries. "
                    f"Error: {error_msg}"
                )

            raise Exception(f"Claude Messages API error: {error_msg}")

    # ==================== JSON COMPLETION ====================

    def _repair_json(self, content: str) -> str:
        """
        Attempt to repair common JSON syntax errors.
        Copied from OpenAI service for compatibility.
        """
        import re

        # Remove markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # Remove trailing commas before } or ]
        content = re.sub(r',(\s*[}\]])', r'\1', content)

        # Add missing commas between object/array items
        content = re.sub(r'}\s*{', '},{', content)
        content = re.sub(r']\s*\[', '],[', content)
        content = re.sub(r'}\s*\[', '},[', content)
        content = re.sub(r']\s*{', '],{', content)

        return content.strip()

    async def generate_json_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        reasoning_effort: Optional[str] = None,
        file_ids: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate JSON completion from Claude.
        Automatically parses response as JSON.
        Same interface as OpenAIService.generate_json_completion().
        """
        result = await self.generate_completion(
            messages=messages,
            temperature=temperature,
            json_mode=True,
            reasoning_effort=reasoning_effort,
            file_ids=file_ids,
            tools=tools,
            model=model or settings.ANTHROPIC_MODEL,
            max_output_tokens=max_output_tokens,
        )

        # Parse JSON content
        logger.info("[Claude] Parsing JSON response...")
        content = result["content"]

        # Try direct parse first
        try:
            parsed_content = json.loads(content)
            result["parsed_content"] = parsed_content
            logger.info("[Claude] JSON parsed successfully (direct parse)")
            logger.info(f"[Claude] Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'Not a dict'}")
        except json.JSONDecodeError as e:
            logger.warning(f"[Claude] Direct JSON parse failed: {str(e)}")
            logger.info("[Claude] Attempting to extract JSON from markdown...")

            # Remove markdown code blocks if present
            if "```json" in content:
                logger.info("[Claude] Found ```json code block, extracting...")
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                logger.info("[Claude] Found ``` code block, extracting...")
                content = content.split("```")[1].split("```")[0].strip()

            # Try parsing after markdown extraction
            try:
                parsed_content = json.loads(content)
                result["parsed_content"] = parsed_content
                logger.info("[Claude] JSON parsed successfully (from markdown)")
                logger.info(f"[Claude] Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'Not a dict'}")
            except json.JSONDecodeError as e2:
                logger.warning(f"[Claude] JSON parsing failed after markdown extraction: {str(e2)}")
                logger.info("[Claude] Attempting to repair JSON...")

                # Try to repair JSON
                try:
                    repaired_content = self._repair_json(content)
                    parsed_content = json.loads(repaired_content)
                    result["parsed_content"] = parsed_content
                    logger.info("[Claude] JSON parsed successfully (after repair)")
                    logger.info(f"[Claude] Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'Not a dict'}")
                except (json.JSONDecodeError, Exception) as e3:
                    error_line = None
                    error_col = None
                    if isinstance(e2, json.JSONDecodeError):
                        error_line = getattr(e2, 'lineno', None)
                        error_col = getattr(e2, 'colno', None)

                    if error_line:
                        lines = content.split('\n')
                        start = max(0, error_line - 3)
                        end = min(len(lines), error_line + 3)
                        context = '\n'.join(lines[start:end])
                        logger.error(f"[Claude] JSON repair failed: {str(e3)}")
                        logger.error(f"[Claude] Error at line {error_line}, col {error_col}")
                        logger.error(f"[Claude] Context around error:\n{context}")
                    else:
                        logger.error(f"[Claude] JSON repair failed: {str(e3)}")
                        logger.error(f"[Claude] Content preview (first 1000 chars): {content[:1000]}")

                    raise Exception(
                        f"Failed to parse JSON response after repair attempts: {str(e2)}\n"
                        f"Error location: line {error_line}, col {error_col if error_col else 'unknown'}"
                    )

        return result

    # ==================== SPECIALIZED METHODS ====================

    async def generate_summary(
        self,
        system_prompt: str,
        user_responses: Dict[str, Any],
        reasoning_effort: str = "medium",
    ) -> Dict[str, Any]:
        """Generate a summary from user responses."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_responses)},
        ]

        return await self.generate_completion(
            messages=messages,
            reasoning_effort=reasoning_effort,
            model=settings.ANTHROPIC_MODEL,
        )

    async def process_scoring(
        self,
        scoring_prompt: str,
        scoring_map: Dict[str, Any],
        task_library: Dict[str, Any],
        diagnostic_questions: Dict[str, Any],
        user_responses: Dict[str, Any],
        file_context: Optional[str] = None,
        file_ids: Optional[List[str]] = None,
        reasoning_effort: str = "low",
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Process user scores using Claude (Part 1 of split pipeline).
        Same interface as OpenAIService.process_scoring().
        """
        logger.info("[Claude] ========== Starting process_scoring ==========")

        file_context_msg = ""
        if file_context:
            file_context_msg = f"\n\n{file_context}"

        question_text_map = {}
        for page in diagnostic_questions.get("pages", []):
            for element in page.get("elements", []):
                question_text_map[element["name"]] = element.get("title", element["name"])

        prompt_text = scoring_prompt

        system_content = (
            f"{prompt_text}\n\n"
            f"Scoring Map: {json.dumps(scoring_map)}\n\n"
            f"IMPORTANT: Respond with valid JSON only. No markdown, no explanations."
            f"{file_context_msg}"
        )

        user_content = (
            f"Question Text Map: {json.dumps(question_text_map)}\n\n"
            f"User Responses: {json.dumps(user_responses)}\n\n"
            f"Generate the complete JSON response as specified in the prompt instructions."
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        scoring_start_time = time.time()

        try:
            logger.info("[Claude] Starting generate_json_completion (this may take several minutes)...")
            result = await self.generate_json_completion(
                messages=messages,
                temperature=0.3,
                reasoning_effort=reasoning_effort,
                file_ids=file_ids if file_ids else None,
                tools=tools,
            )
            scoring_elapsed = time.time() - scoring_start_time
            logger.info(f"[Claude] generate_json_completion completed in {scoring_elapsed:.2f} seconds ({scoring_elapsed / 60:.2f} minutes)")
            return result
        except Exception as e:
            scoring_elapsed = time.time() - scoring_start_time
            logger.error(f"[Claude] generate_json_completion failed after {scoring_elapsed:.2f} seconds ({scoring_elapsed / 60:.2f} minutes)")
            logger.error(f"[Claude] Error: {str(e)}")
            logger.error("[Claude] Full exception details:", exc_info=True)
            raise

    async def generate_report(
        self,
        report_prompt: str,
        scored_rows: List[Dict[str, Any]],
        all_responses: List[Dict[str, Any]],
        module_averages: Dict[str, Any],
        file_insights: str,
        task_library: Dict[str, Any],
        summary: str,
        reasoning_effort: str = "medium",
    ) -> Dict[str, Any]:
        """
        Generate advisor report from pre-scored data (Part 2 of split pipeline).
        Same interface as OpenAIService.generate_report().
        """
        logger.info("[Claude] ========== Starting generate_report (Part 2) ==========")

        prompt_text = report_prompt.replace(
            "{MODULE_TASK_LIBRARY}",
            json.dumps(task_library, indent=2),
        )

        system_content = prompt_text

        user_content = (
            f"Diagnostic Summary:\n{summary}\n\n"
            f"Module Averages (pre-computed and verified):\n{json.dumps(module_averages, indent=2)}\n\n"
            f"File Insights:\n{file_insights if file_insights else 'No uploaded documents.'}\n\n"
            f"Scored Rows ({len(scored_rows)} items):\n{json.dumps(scored_rows)}\n\n"
            f"All Responses ({len(all_responses)} items):\n{json.dumps(all_responses)}\n\n"
            f"Generate the complete JSON response as specified in the prompt instructions."
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        report_start_time = time.time()

        try:
            logger.info("[Claude] Starting report generation (this may take several minutes)...")
            result = await self.generate_json_completion(
                messages=messages,
                temperature=0.3,
                reasoning_effort=reasoning_effort,
            )
            report_elapsed = time.time() - report_start_time
            logger.info(f"[Claude] Report generation completed in {report_elapsed:.2f} seconds ({report_elapsed / 60:.2f} minutes)")
            return result
        except Exception as e:
            report_elapsed = time.time() - report_start_time
            logger.error(f"[Claude] Report generation failed after {report_elapsed:.2f} seconds ({report_elapsed / 60:.2f} minutes)")
            logger.error(f"[Claude] Error: {str(e)}")
            logger.error("[Claude] Full exception details:", exc_info=True)
            raise

    async def generate_advice(
        self,
        advice_prompt: str,
        scoring_data: Dict[str, Any],
        reasoning_effort: str = "medium",
    ) -> Dict[str, Any]:
        """Generate personalized advice based on scoring results."""
        messages = [
            {"role": "system", "content": advice_prompt},
            {"role": "user", "content": json.dumps(scoring_data)},
        ]

        return await self.generate_completion(
            messages=messages,
            reasoning_effort=reasoning_effort,
            model=settings.ANTHROPIC_MODEL,
        )

    async def generate_tasks(
        self,
        task_prompt: str,
        diagnostic_summary: str,
        json_extract: Dict[str, Any],
        roadmap: List[Dict[str, Any]],
        reasoning_effort: str = "medium",
    ) -> Dict[str, Any]:
        """
        Generate tasks based on diagnostic results.
        Same interface as OpenAIService.generate_tasks().
        """
        context = (
            f"You are an expert business advisor named 'Trinity'. "
            f"Based on the following diagnostic data, provide a JSON object with a 'tasks' array containing tasks "
            f"a business owner should action within the next 30 days.\n\n"
            f"CRITICAL RULE: Every task you generate MUST be directly supported by specific data in the "
            f"Diagnostic Data (Q&A) or the Priority Roadmap below. DO NOT generate generic business advice "
            f"or tasks that are not directly evidenced by this business's actual responses. "
            f"If a module scored Green (>= 4.0), do NOT create tasks for it unless the Q&A reveals a specific gap. "
            f"Quality and accuracy matter far more than quantity.\n\n"
            f"Summary: {diagnostic_summary}\n\n"
            f"Diagnostic Data (Q&A): {json.dumps(json_extract)}\n\n"
            f"Priority Roadmap (Modules by Priority):\n{json.dumps(roadmap, indent=2)}\n\n"
            f"Focus on the highest priority modules (lowest rank = highest priority). "
            f"Only create tasks for modules with Amber or Red RAG status.\n\n"
            f'Template: {{"tasks": [{{'
            f'"title": "Task Title (Keep it short and concise)", '
            f'"description": "Task description with step-by-step instructions. Every step must be in a new line with 1. 2. 3. Numbering", '
            f'"category": "general|legal-licensing|financial|operations|human-resources|customers|competitive-forces|due-diligence|tax", '
            f'"priority": "low|medium|high|critical", '
            f'"data_reference": "Brief reference to the specific Q&A response(s) or roadmap finding that justifies this task"'
            f"}}]}}\n\n"
            f"{task_prompt}"
        )

        messages = [
            {
                "role": "system",
                "content": context,
            },
            {
                "role": "user",
                "content": (
                    f"Generate actionable tasks in JSON format based ONLY on the supplied diagnostic data. "
                    f"IMPORTANT: Do NOT invent or assume issues that are not evidenced in the data. "
                    f"Each task must be directly traceable to a specific Q&A response or roadmap finding. "
                    f"Only create tasks for Amber/Red modules -- skip Green modules unless there is a clear specific gap in the Q&A. "
                    f"Generate only as many tasks as the data genuinely supports (typically 3-8 tasks). "
                    f"It is better to have fewer accurate tasks than many irrelevant ones. "
                    f"Include a 'data_reference' field in each task citing the specific evidence. "
                    f"Provide detailed descriptions with step-by-step instructions for each task. "
                    f'CRITICAL: Return a JSON OBJECT with a \'tasks\' key containing an array of task objects. '
                    f'Format: {{"tasks": [{{task1}}, {{task2}}, ...]}}. '
                    f"Return ONLY the JSON object, no markdown, no explanations."
                ),
            },
        ]

        return await self.generate_json_completion(
            messages=messages,
            reasoning_effort=reasoning_effort,
            model=settings.ANTHROPIC_MODEL,
        )

    # ==================== FILE UPLOAD ====================

    async def upload_file(
        self,
        file_path: str,
        purpose: str = "user_data",
    ) -> Optional[Dict[str, Any]]:
        """
        Upload a file to Claude Files API for analysis.
        Same interface as OpenAIService.upload_file().

        Args:
            file_path: Path to the file to upload
            purpose: Purpose of the file (kept for interface compatibility)

        Returns:
            Dictionary with file information including 'id', or None if failed
        """
        try:
            if not os.path.exists(file_path):
                print(f" File not found at path: {file_path}")
                raise FileNotFoundError(f"File not found: {file_path}")

            print(f" File found at path: {file_path}")

            filename = os.path.basename(file_path)
            mime_type = self._get_mime_type(filename)

            with open(file_path, "rb") as f:
                file_data = f.read()

            response = await self.client.beta.files.upload(
                file=(filename, file_data, mime_type),
            )

            logger.info(f"[Claude] File uploaded: {response.id}")
            return {
                "id": response.id,
                "filename": filename,
                "bytes": len(file_data),
                "purpose": purpose,
                "created_at": getattr(response, "created_at", None),
            }

        except Exception as e:
            logger.error(f"[Claude] File upload error: {str(e)}", exc_info=True)
            return None


# Singleton instance
claude_service = ClaudeService()
