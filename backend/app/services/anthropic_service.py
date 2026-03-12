"""
Anthropic Claude service for LLM interactions using Messages API.
Drop-in replacement for OpenAI service — same public interface.
To switch back to OpenAI: comment out this file's usage and uncomment openai_service.py
"""
from typing import Dict, Any, List, Optional, Tuple
import json
import os
import time
import asyncio
from anthropic import AsyncAnthropic
from app.config import settings
import logging
import httpx

logger = logging.getLogger(__name__)


# Model mapping from OpenAI model names to Anthropic equivalents
# Used for backward compatibility if callers pass OpenAI model names
MODEL_MAP = {
    "gpt-5.2": "claude-sonnet-4-6",
    "gpt-5-nano": "claude-haiku-4-5",
    "gpt-4o": "claude-sonnet-4-6",
    "gpt-4o-mini": "claude-haiku-4-5",
    "gpt-4-turbo": "claude-sonnet-4-6",
}

# Beta header required for Files API
FILES_API_BETA = "files-api-2025-04-14"

# Code Execution Tool type identifier
CODE_EXECUTION_TOOL_TYPE = "code_execution_20250825"


class AnthropicService:
    """Service for interacting with Anthropic Claude Messages API"""

    # Class-level client that will be initialized once at startup
    _client: Optional[AsyncAnthropic] = None

    def __init__(self):
        """Initialize Anthropic service (client is initialized separately at startup)"""
        self.temperature = settings.ANTHROPIC_TEMPERATURE

    @classmethod
    def initialize_client(cls):
        """Initialize the Anthropic client once at application startup"""
        if cls._client is None:
            cls._client = AsyncAnthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=1800.0,      # 30 minutes for long requests
                    write=10.0,
                    pool=10.0
                ),
                max_retries=2
            )
            if settings.ANTHROPIC_TIMEOUT is not None:
                timeout_str = f"{settings.ANTHROPIC_TIMEOUT} seconds ({settings.ANTHROPIC_TIMEOUT/60:.1f} minutes)"
            else:
                timeout_str = "no timeout"
            logger.info(f"Anthropic client initialized with timeout: {timeout_str}")
        return cls._client

    @property
    def client(self) -> AsyncAnthropic:
        """Get the shared Anthropic client instance"""
        if AnthropicService._client is None:
            raise RuntimeError(
                "Anthropic client not initialized. Call AnthropicService.initialize_client() "
                "at application startup (e.g., in main.py startup event)."
            )
        return AnthropicService._client

    def _resolve_model(self, model: str) -> str:
        """Resolve model name — maps OpenAI model names to Anthropic equivalents"""
        if model in MODEL_MAP:
            resolved = MODEL_MAP[model]
            logger.info(f"[Anthropic] Mapped model '{model}' -> '{resolved}'")
            return resolved
        return model

    def _prepare_messages(
        self,
        messages: List[Dict[str, str]],
        file_ids: Optional[List[str]] = None,
        file_types: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Convert chat messages to Anthropic Messages API format.
        Extracts system messages into a separate system prompt (top-level param).
        Supports file attachments in the last user message.

        Args:
            messages: List of message objects with 'role' and 'content'
            file_ids: Optional list of Anthropic file IDs to attach to the last user message
            file_types: Optional dict mapping file_id -> extension (e.g. "pdf", "csv", "xlsx")
                       Used to determine the correct content block type.
                       If not provided, defaults to "document" type for all files.

        Returns:
            Tuple of (system_prompt, messages_list)
        """
        system_parts = []
        api_messages = []

        for idx, msg in enumerate(messages):
            role = msg["role"]
            content = msg["content"]

            # Extract system messages into the top-level system parameter
            if role == "system" or role == "developer":
                system_parts.append(content)
                continue

            # Only user and assistant roles are allowed in Anthropic messages
            if role not in ("user", "assistant"):
                logger.warning(f"[Anthropic] Skipping message with unsupported role: {role}")
                continue

            # For the last user message, attach files if provided
            is_last_user_message = (
                idx == len(messages) - 1
                and role == "user"
                and file_ids
                and len(file_ids) > 0
            )

            if is_last_user_message:
                content_array = []

                # Add files first
                for file_id in file_ids:
                    ext = ""
                    if file_types and file_id in file_types:
                        ext = file_types[file_id].lower().lstrip(".")

                    if ext in ("csv", "xlsx", "xls", "txt", "json", "xml", "md", "py"):
                        # Data/text files: use container_upload for code execution
                        content_array.append({
                            "type": "container_upload",
                            "file_id": file_id
                        })
                    elif ext in ("jpg", "jpeg", "png", "gif", "webp"):
                        # Images: use image block
                        content_array.append({
                            "type": "image",
                            "source": {
                                "type": "file",
                                "file_id": file_id
                            }
                        })
                    else:
                        # PDFs and other documents: use document block
                        content_array.append({
                            "type": "document",
                            "source": {
                                "type": "file",
                                "file_id": file_id
                            }
                        })

                # Add text content
                content_array.append({
                    "type": "text",
                    "text": content
                })

                api_messages.append({
                    "role": role,
                    "content": content_array
                })
            else:
                # Regular message without files
                api_messages.append({
                    "role": role,
                    "content": content
                })

        system_prompt = "\n\n".join(system_parts)
        return system_prompt, api_messages

    def _normalize_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """
        Normalize tool definitions from OpenAI format to Anthropic format.
        Maps code_interpreter -> code_execution_20250825.
        """
        if not tools:
            return None

        normalized: List[Dict[str, Any]] = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            tool_type = t.get("type", "")

            # Map OpenAI's code_interpreter to Anthropic's code_execution
            if tool_type == "code_interpreter":
                normalized.append({
                    "type": CODE_EXECUTION_TOOL_TYPE,
                    "name": "code_execution"
                })
            elif tool_type == CODE_EXECUTION_TOOL_TYPE:
                # Already in Anthropic format
                normalized.append(t)
            else:
                # Pass through other tool types
                normalized.append(t)

        return normalized if normalized else None

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        json_mode: bool = False,
        reasoning_effort: Optional[str] = None,  # Kept for interface compat, ignored
        file_ids: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = "claude-haiku-4-5",
        max_output_tokens: Optional[int] = None,
        file_types: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate completion from Anthropic Claude using Messages API.

        Args:
            messages: List of message objects with 'role' and 'content'
                     ('system' role will be extracted to top-level system param)
            temperature: Override default temperature
            json_mode: Enable JSON mode (adds instruction to system prompt)
            reasoning_effort: IGNORED — kept for interface compatibility with OpenAI service
            file_ids: Optional list of Anthropic file IDs to attach to the last user message
            tools: Optional list of tool definitions (code_interpreter will be mapped)
            model: Model to use for the response
            max_output_tokens: Maximum output tokens (required by Anthropic, defaults to settings)
            file_types: Optional dict mapping file_id -> extension for content block routing
        Returns:
            Dictionary containing response and metadata (same shape as OpenAI service)
        """
        try:
            # Resolve model name (handles OpenAI model names)
            model = self._resolve_model(model)
            logger.info(f"[Anthropic] Model: {model}")

            # Prepare messages — extract system prompt, format content blocks
            system_prompt, api_messages = self._prepare_messages(
                messages, file_ids=file_ids, file_types=file_types
            )

            # If JSON mode, append instruction to system prompt
            if json_mode:
                json_instruction = (
                    "\n\nIMPORTANT: You must respond with valid JSON only. "
                    "No markdown code blocks, no explanations, no text outside the JSON object. "
                    "Return ONLY the raw JSON."
                )
                system_prompt = (system_prompt + json_instruction) if system_prompt else json_instruction.strip()

            # Normalize tools (map code_interpreter -> code_execution)
            normalized_tools = self._normalize_tools(tools)

            # Prepare API parameters
            params: Dict[str, Any] = {
                "model": model,
                "max_tokens": max_output_tokens or settings.ANTHROPIC_MAX_TOKENS,
                "messages": api_messages,
                "betas": [FILES_API_BETA],
            }

            if system_prompt:
                params["system"] = system_prompt

            if temperature is not None:
                params["temperature"] = temperature

            if normalized_tools:
                params["tools"] = normalized_tools

            start_time = time.time()
            try:
                logger.info("[Anthropic API] Making API call to Anthropic Messages API...")
                response = await self.client.beta.messages.create(**params)

                elapsed_time = time.time() - start_time
                logger.info(f"[Anthropic API] API call succeeded in {elapsed_time:.2f} seconds")

            except Exception as executor_error:
                elapsed_time = time.time() - start_time
                error_msg = str(executor_error)
                error_type = type(executor_error).__name__

                logger.error(f"[Anthropic API] API call failed after {elapsed_time:.2f} seconds")
                logger.error(f"[Anthropic API] Error type: {error_type}")
                logger.error(f"[Anthropic API] Error message: {error_msg}")

                if elapsed_time >= 600:
                    logger.error(f"[Anthropic API] Request took {elapsed_time:.2f} seconds - likely a timeout")

                status_code = None
                if hasattr(executor_error, 'status_code'):
                    status_code = executor_error.status_code
                elif hasattr(executor_error, 'response'):
                    if hasattr(executor_error.response, 'status_code'):
                        status_code = executor_error.response.status_code

                if status_code:
                    logger.error(f"[Anthropic API] HTTP Status Code: {status_code}")
                    if status_code == 500:
                        logger.error(f"[Anthropic API] Server returned 500 Internal Server Error")
                    elif status_code == 429:
                        logger.error(f"[Anthropic API] Rate limit exceeded (429). SDK will retry automatically.")
                    elif status_code >= 500:
                        logger.error(f"[Anthropic API] Server error ({status_code}). SDK will retry automatically.")

                logger.error(f"[Anthropic API] Full exception details:", exc_info=True)
                raise

            # ── Extract content from response ──
            content = ""
            text_chunks: List[str] = []
            code_execution_chunks: List[str] = []

            for block in response.content:
                block_type = getattr(block, "type", None)

                if block_type == "text":
                    text_chunks.append(block.text)
                elif block_type == "code_execution_result":
                    # Extract stdout/logs from code execution results
                    result_content = getattr(block, "content", None)
                    if result_content:
                        if isinstance(result_content, str):
                            code_execution_chunks.append(result_content)
                        elif isinstance(result_content, list):
                            for item in result_content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    code_execution_chunks.append(item.get("text", ""))
                                elif hasattr(item, "text"):
                                    code_execution_chunks.append(item.text)

            # Primary: text content
            content = "\n".join(text_chunks).strip()

            # Fallback: code execution results if no text content
            if not content and code_execution_chunks:
                content = "\n".join(code_execution_chunks).strip()
                logger.info(f"[Anthropic API] Recovered content from code execution results ({len(code_execution_chunks)} chunks)")

            # Extract token usage
            input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
            output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
            total_tokens = input_tokens + output_tokens
            stop_reason = getattr(response, 'stop_reason', 'end_turn')

            logger.info(f"[Anthropic API] Token usage - Total: {total_tokens}, Input: {input_tokens}, Output: {output_tokens}")
            logger.info(f"[Anthropic API] Stop reason: {stop_reason}")

            # Build output summary for debugging
            output_summary: List[Dict[str, Any]] = []
            for block in response.content:
                block_type = getattr(block, "type", None)
                summary_entry: Dict[str, Any] = {"type": block_type}
                if block_type == "text":
                    summary_entry["text_length"] = len(getattr(block, "text", ""))
                elif block_type == "code_execution_result":
                    summary_entry["has_content"] = bool(getattr(block, "content", None))
                output_summary.append(summary_entry)

            if not content:
                logger.warning(
                    "[Anthropic API] Empty content returned. "
                    "stop_reason=%s tokens_used=%s response_id=%s output_summary=%s",
                    stop_reason, total_tokens, getattr(response, "id", None), output_summary,
                )

            # Return structured response (same shape as OpenAI service)
            return {
                "content": content,
                "model": model,
                "tokens_used": total_tokens,
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "finish_reason": stop_reason,
                "response_id": getattr(response, "id", None),
                "output_summary": output_summary,
            }

        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__

            logger.error(f"[Anthropic API] API call failed after all retries")
            logger.error(f"[Anthropic API] Final error type: {error_type}")
            logger.error(f"[Anthropic API] Final error message: {error_msg}")
            logger.error(f"[Anthropic API] Full exception traceback:", exc_info=True)

            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                logger.error(f"[Anthropic API] Timeout error detected. Timeout setting: {settings.ANTHROPIC_TIMEOUT} seconds")
                raise Exception(f"Anthropic API request timed out after {settings.ANTHROPIC_TIMEOUT} seconds. Error: {error_msg}")

            if "api key" in error_msg.lower() or "authentication" in error_msg.lower():
                logger.error("[Anthropic API] Authentication error detected")
                raise Exception(f"Anthropic API authentication failed. Please check your ANTHROPIC_API_KEY. Error: {error_msg}")

            if "500" in error_msg or "Internal Server Error" in error_msg:
                logger.error("[Anthropic API] Server returned 500 after all retries")
                raise Exception(f"Anthropic API returned 500 Internal Server Error after all retries. Please try again later. Error: {error_msg}")

            if "429" in error_msg or "rate limit" in error_msg.lower():
                logger.error("[Anthropic API] Rate limit error after all retries")
                raise Exception(f"Anthropic API rate limit exceeded after all retries. Please wait and try again later. Error: {error_msg}")

            raise Exception(f"Anthropic Messages API error: {error_msg}")

    def _repair_json(self, content: str) -> str:
        """
        Attempt to repair common JSON syntax errors.

        Args:
            content: Potentially malformed JSON string

        Returns:
            Repaired JSON string
        """
        import re

        # Remove markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # Remove trailing commas before } or ]
        content = re.sub(r',(\s*[}\]])', r'\1', content)

        # Try to add missing commas between object/array items
        content = re.sub(r'}\s*{', '},{', content)
        content = re.sub(r']\s*\[', '],[', content)
        content = re.sub(r'}\s*\[', '},[', content)
        content = re.sub(r']\s*{', '],{', content)

        return content.strip()

    async def generate_json_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        reasoning_effort: Optional[str] = None,  # Kept for interface compat, ignored
        file_ids: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        file_types: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate JSON completion from Anthropic Claude using Messages API.
        Automatically parses response as JSON.

        Args:
            messages: List of message objects with 'role' and 'content'
            temperature: Override default temperature
            reasoning_effort: IGNORED — kept for interface compatibility
            file_ids: Optional list of Anthropic file IDs to attach
            tools: Optional list of tool definitions
            model: Model to use (defaults to settings.ANTHROPIC_MODEL)
            max_output_tokens: Maximum output tokens
            file_types: Optional dict mapping file_id -> extension

        Returns:
            Dictionary containing parsed JSON response and metadata
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
            file_types=file_types,
        )

        # Parse JSON content
        logger.info("[Anthropic] Parsing JSON response...")
        content = result["content"]

        # Try direct parse first
        try:
            parsed_content = json.loads(content)
            result["parsed_content"] = parsed_content
            logger.info("[Anthropic] JSON parsed successfully (direct parse)")
            logger.info(f"[Anthropic] Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'Not a dict'}")
        except json.JSONDecodeError as e:
            logger.warning(f"[Anthropic] Direct JSON parse failed: {str(e)}")
            logger.info("[Anthropic] Attempting to extract JSON from markdown...")

            # Remove markdown code blocks if present
            if "```json" in content:
                logger.info("[Anthropic] Found ```json code block, extracting...")
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                logger.info("[Anthropic] Found ``` code block, extracting...")
                content = content.split("```")[1].split("```")[0].strip()

            # Try parsing after markdown extraction
            try:
                parsed_content = json.loads(content)
                result["parsed_content"] = parsed_content
                logger.info("[Anthropic] JSON parsed successfully (from markdown)")
                logger.info(f"[Anthropic] Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'Not a dict'}")
            except json.JSONDecodeError as e2:
                logger.warning(f"[Anthropic] JSON parsing failed after markdown extraction: {str(e2)}")
                logger.info("[Anthropic] Attempting to repair JSON...")

                # Try to repair JSON
                try:
                    repaired_content = self._repair_json(content)
                    parsed_content = json.loads(repaired_content)
                    result["parsed_content"] = parsed_content
                    logger.info("[Anthropic] JSON parsed successfully (after repair)")
                    logger.info(f"[Anthropic] Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'Not a dict'}")
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
                        logger.error(f"[Anthropic] JSON repair failed: {str(e3)}")
                        logger.error(f"[Anthropic] Error at line {error_line}, col {error_col}")
                        logger.error(f"[Anthropic] Context around error:\n{context}")
                    else:
                        logger.error(f"[Anthropic] JSON repair failed: {str(e3)}")
                        logger.error(f"[Anthropic] Content preview (first 1000 chars): {content[:1000]}")

                    raise Exception(f"Failed to parse JSON response after repair attempts: {str(e2)}\nError location: line {error_line}, col {error_col if error_col else 'unknown'}")

        return result

    async def generate_summary(
        self,
        system_prompt: str,
        user_responses: Dict[str, Any],
        reasoning_effort: str = "medium"  # Ignored — kept for interface compat
    ) -> Dict[str, Any]:
        """
        Generate a summary from user responses.

        Args:
            system_prompt: System prompt for the summary
            user_responses: User's diagnostic responses
            reasoning_effort: IGNORED — kept for interface compatibility

        Returns:
            Dictionary containing summary and metadata
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_responses)}
        ]

        return await self.generate_completion(
            messages=messages,
            model=settings.ANTHROPIC_MODEL
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
        reasoning_effort: str = "low",  # Ignored — kept for interface compat
        tools: Optional[List[Dict[str, Any]]] = None,
        file_types: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Process user scores using Claude with the scoring map.
        This is the core AI processing step.

        Args:
            scoring_prompt: Instructions for scoring
            scoring_map: Mapping of questions to scores
            task_library: Library of predefined tasks
            diagnostic_questions: Full diagnostic survey structure
            user_responses: User's answers
            file_context: Context about uploaded files
            file_ids: List of Anthropic file IDs to attach for AI analysis
            reasoning_effort: IGNORED — kept for interface compatibility
            tools: Optional tool definitions (code_interpreter mapped to code_execution)
            file_types: Optional dict mapping file_id -> extension

        Returns:
            Dictionary containing scoring results, roadmap, and advisor report
        """
        logger.info("[Anthropic] ========== Starting process_scoring ==========")

        file_context_msg = ""
        if file_context:
            file_context_msg = f"\n\n{file_context}"

        question_text_map = {}
        for page in diagnostic_questions.get("pages", []):
            for element in page.get("elements", []):
                question_text_map[element["name"]] = element.get("title", element["name"])

        system_content = (
            f"{scoring_prompt}\n\n"
            f"Scoring Map: {json.dumps(scoring_map)}\n\n"
            f"Process User Responses using Scoring Map and store as scored_rows.\n"
            f"Join scored_rows array with roadmap array in the same json structure.\n\n"
            f"Task Library: {json.dumps(task_library)}\n\n"
            f"IMPORTANT: Respond with valid JSON only. No markdown, no explanations."
            f"{file_context_msg}"
        )

        user_content = (
            f"Question Text Map: {json.dumps(question_text_map)}\n\n"
            f"User Responses: {json.dumps(user_responses)}\n\n"
            f"Generate a complete JSON response with scored_rows, roadmap, and advisorReport."
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]

        scoring_start_time = time.time()

        try:
            logger.info("[Anthropic] Starting generate_json_completion (this may take several minutes)...")
            result = await self.generate_json_completion(
                messages=messages,
                temperature=0.3,
                file_ids=file_ids if file_ids else None,
                tools=tools,
                file_types=file_types,
            )
            scoring_elapsed = time.time() - scoring_start_time
            logger.info(f"[Anthropic] generate_json_completion completed successfully in {scoring_elapsed:.2f} seconds ({scoring_elapsed/60:.2f} minutes)")
            return result
        except Exception as e:
            scoring_elapsed = time.time() - scoring_start_time
            error_msg = str(e)
            logger.error(f"[Anthropic] generate_json_completion failed after {scoring_elapsed:.2f} seconds ({scoring_elapsed/60:.2f} minutes)")
            logger.error(f"[Anthropic] Error: {error_msg}")
            logger.error(f"[Anthropic] Full exception details:", exc_info=True)
            raise

    async def generate_advice(
        self,
        advice_prompt: str,
        scoring_data: Dict[str, Any],
        reasoning_effort: str = "medium"  # Ignored — kept for interface compat
    ) -> Dict[str, Any]:
        """
        Generate personalized advice based on scoring results.

        Args:
            advice_prompt: Prompt for generating advice
            scoring_data: Complete scoring data with roadmap and advisor report
            reasoning_effort: IGNORED — kept for interface compatibility

        Returns:
            Dictionary containing advice and metadata
        """
        messages = [
            {"role": "system", "content": advice_prompt},
            {"role": "user", "content": json.dumps(scoring_data)}
        ]

        return await self.generate_completion(
            messages=messages,
            model=settings.ANTHROPIC_MODEL
        )

    async def generate_tasks(
        self,
        task_prompt: str,
        diagnostic_summary: str,
        json_extract: Dict[str, Any],
        roadmap: List[Dict[str, Any]],
        reasoning_effort: str = "medium"  # Ignored — kept for interface compat
    ) -> Dict[str, Any]:
        """
        Generate tasks based on diagnostic results.

        Args:
            task_prompt: Prompt for task generation
            diagnostic_summary: Summary of the diagnostic
            json_extract: Q&A extract (question text -> answer pairs)
            roadmap: Priority roadmap with module rankings
            reasoning_effort: IGNORED — kept for interface compatibility

        Returns:
            Dictionary containing generated tasks and metadata
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
            f"Template: {{\"tasks\": [{{"
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
                "content": context
            },
            {
                "role": "user",
                "content": (
                    f"Generate actionable tasks in JSON format based ONLY on the supplied diagnostic data. "
                    f"IMPORTANT: Do NOT invent or assume issues that are not evidenced in the data. "
                    f"Each task must be directly traceable to a specific Q&A response or roadmap finding. "
                    f"Only create tasks for Amber/Red modules - skip Green modules unless there is a clear specific gap in the Q&A. "
                    f"Generate only as many tasks as the data genuinely supports (typically 3-8 tasks). "
                    f"It is better to have fewer accurate tasks than many irrelevant ones. "
                    f"Include a 'data_reference' field in each task citing the specific evidence. "
                    f"Provide detailed descriptions with step-by-step instructions for each task. "
                    f"CRITICAL: Return a JSON OBJECT with a 'tasks' key containing an array of task objects. "
                    f"Format: {{\"tasks\": [{{task1}}, {{task2}}, ...]}}. "
                    f"Return ONLY the JSON object, no markdown, no explanations."
                )
            }
        ]

        return await self.generate_json_completion(
            messages=messages,
            model=settings.ANTHROPIC_MODEL
        )

    async def upload_file(
        self,
        file_path: str,
        purpose: str = "user_data"
    ) -> Optional[Dict[str, Any]]:
        """
        Upload a file to Anthropic for analysis.

        Args:
            file_path: Path to the file to upload
            purpose: Purpose of the file (kept for interface compat, not used by Anthropic)

        Returns:
            Dictionary with file information including 'id', or None if failed
        """
        try:
            if not os.path.exists(file_path):
                print(f" File not found at path: {file_path}")
                raise FileNotFoundError(f"File not found: {file_path}")

            print(f" File found at path: {file_path}")

            with open(file_path, 'rb') as file:
                response = await self.client.beta.files.upload(file=file)

            logger.info(f"[Anthropic] File uploaded: {response.id}")
            return {
                "id": response.id,
                "filename": response.filename,
                "bytes": getattr(response, 'size_bytes', None),
                "purpose": purpose,
                "created_at": getattr(response, 'created_at', None)
            }

        except Exception as e:
            logger.error(f"[Anthropic] File upload error: {str(e)}", exc_info=True)
            return None


# Singleton instance
anthropic_service = AnthropicService()
