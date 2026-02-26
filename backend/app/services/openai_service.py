"""
OpenAI service for GPT interactions using Responses API
"""
from typing import Dict, Any, List, Optional
import json
import os

import time
import asyncio
from openai import AsyncOpenAI
from app.config import settings
import logging
import httpx
logger = logging.getLogger(__name__)
import time


class OpenAIService:
    """Service for interacting with OpenAI Responses API"""
    
    # Class-level client that will be initialized once at startup
    _client: Optional[AsyncOpenAI] = None
    
    def __init__(self):
        """Initialize OpenAI service (client is initialized separately at startup)"""
        self.temperature = settings.OPENAI_TEMPERATURE
    
    @classmethod
    def initialize_client(cls):
        """Initialize the OpenAI client once at application startup"""
        if cls._client is None:
            # Set timeout (default: 3600 seconds = 1 hour for long-running processes)
            cls._client = AsyncOpenAI(  # ← Changed from OpenAI to AsyncOpenAI
                api_key=settings.OPENAI_API_KEY,
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=1800.0,      # ← 30 minutes for long requests
                    write=10.0,
                    pool=10.0
                ),
                max_retries=2
            )
            # Safely format timeout string (handle None case)
            if settings.OPENAI_TIMEOUT is not None:
                timeout_str = f"{settings.OPENAI_TIMEOUT} seconds ({settings.OPENAI_TIMEOUT/60:.1f} minutes)"
            else:
                timeout_str = "no timeout"
            logger.info(f"OpenAI client initialized with timeout: {timeout_str}")
        return cls._client
    
    @property
    def client(self) -> AsyncOpenAI:
        """Get the shared OpenAI client instance"""
        if OpenAIService._client is None:
            raise RuntimeError(
                "OpenAI client not initialized. Call OpenAIService.initialize_client() "
                "at application startup (e.g., in main.py startup event)."
            )
        return OpenAIService._client
    
    def _convert_messages_to_input(
        self, 
        messages: List[Dict[str, str]],
        file_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert chat completion messages to Responses API input format.
        Changes 'system' role to 'developer' role.
        Supports file attachments in the last user message.
        
        Args:
            messages: List of message objects with 'role' and 'content'
            file_ids: Optional list of OpenAI file IDs to attach to the last user message
            
        Returns:
            List of input messages with converted roles and file attachments
        """
        input_messages = []
        
        for idx, msg in enumerate(messages):
            role = msg["role"]
            # Convert 'system' role to 'developer' for Responses API
            if role == "system":
                role = "developer"
            
            # For the last user message, attach files if provided
            is_last_user_message = (
                idx == len(messages) - 1 and 
                msg["role"] == "user" and 
                file_ids and 
                len(file_ids) > 0
            )
            
            if is_last_user_message:
                # Build content array with files and text
                content_array = []
                
                # Add files first
                for file_id in file_ids:
                    content_array.append({
                        "type": "input_file",
                        "file_id": file_id
                    })
                
                # Add text content
                content_array.append({
                    "type": "input_text",
                    "text": msg["content"]
                })
                
                input_messages.append({
                    "role": role,
                    "content": content_array
                })
            else:
                # Regular message without files
                input_messages.append({
                    "role": role,
                    "content": msg["content"]
                })
        
        return input_messages
    
    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        json_mode: bool = False,
        reasoning_effort: Optional[str] = None,
        file_ids: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = "gpt-5-nano",
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate completion from OpenAI using Responses API.
        
        Args:
            messages: List of message objects with 'role' and 'content'
                     ('system' role will be converted to 'developer')
            temperature: Override default temperature
            json_mode: Enable JSON mode output
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            file_ids: Optional list of OpenAI file IDs to attach to the last user message
            model: Model to use for the response
        Returns:
            Dictionary containing response and metadata
        """
        try:
            # Convert messages to input format (with files if provided)
            input_messages = self._convert_messages_to_input(messages, file_ids=file_ids)

            logger.info(f"GPT Model: {model}")
            
            # Prepare parameters
            params = {
                "model": model,
                "input": input_messages,
                "max_output_tokens": max_output_tokens,
            }
            
            if json_mode:
                params["text"] = {"format": {"type": "json_object"}}
            
            if reasoning_effort:
                params["reasoning"] = {"effort": reasoning_effort}

            if tools:
                normalized_tools: List[Dict[str, Any]] = []
                for t in tools:
                    if not isinstance(t, dict):
                        continue
                    if t.get("type") == "code_interpreter" and "container" not in t:
                        normalized_tools.append({**t, "container": {"type": "auto"}})
                    else:
                        normalized_tools.append(t)
                params["tools"] = normalized_tools
            
            start_time = time.time()
            try:
                logger.info("[OpenAI API] Making API call to OpenAI Responses API...")
                # Must be API call here; logger.info(msg, ...) requires message as first positional arg
                response = await self.client.responses.create(**params)
                
                elapsed_time = time.time() - start_time
                logger.info(f"[OpenAI API] ✅ API call succeeded in {elapsed_time:.2f} seconds")
                logger.info(f"[OpenAI API] ✅ Received response from OpenAI API")
                
            except Exception as executor_error:
                elapsed_time = time.time() - start_time
                error_msg = str(executor_error)
                error_type = type(executor_error).__name__
                
                # Log detailed error information
                logger.error(f"[OpenAI API] ❌ API call failed after {elapsed_time:.2f} seconds")
                logger.error(f"[OpenAI API] Error type: {error_type}")
                logger.error(f"[OpenAI API] Error message: {error_msg}")
                
                # Check if it was a timeout
                if elapsed_time >= 600:  # 10 minutes
                    logger.error(f"[OpenAI API] ⚠️ Request took {elapsed_time:.2f} seconds - likely a timeout")
                elif elapsed_time >= 1800:  # 30 minutes
                    logger.error(f"[OpenAI API] ⚠️⚠️ Request took {elapsed_time:.2f} seconds - exceeded read timeout!")
                
                # Check for HTTP status codes in error message or attributes
                status_code = None
                if hasattr(executor_error, 'status_code'):
                    status_code = executor_error.status_code
                elif hasattr(executor_error, 'response'):
                    if hasattr(executor_error.response, 'status_code'):
                        status_code = executor_error.response.status_code
                
                if status_code:
                    logger.error(f"[OpenAI API] HTTP Status Code: {status_code}")
                    if status_code == 500:
                        logger.error(f"[OpenAI API] ⚠️ OpenAI server returned 500 Internal Server Error")
                        logger.error(f"[OpenAI API] This may be a temporary issue. SDK will retry automatically (max_retries={self.client.max_retries})")
                    elif status_code == 429:
                        logger.error(f"[OpenAI API] ⚠️ Rate limit exceeded (429). SDK will retry automatically.")
                    elif status_code >= 500:
                        logger.error(f"[OpenAI API] ⚠️ Server error ({status_code}). SDK will retry automatically.")
                
                # Check error message for status codes
                if "500" in error_msg or "Internal Server Error" in error_msg:
                    logger.error(f"[OpenAI API] ⚠️ Detected 500 Internal Server Error in error message")
                    logger.error(f"[OpenAI API] SDK max_retries setting: {self.client.max_retries}")
                    logger.error(f"[OpenAI API] The SDK will automatically retry up to {self.client.max_retries} times")
                
                if "429" in error_msg or "rate limit" in error_msg.lower():
                    logger.error(f"[OpenAI API] ⚠️ Rate limit detected. SDK will retry automatically.")
                
                # Log full exception details
                logger.error(f"[OpenAI API] Full exception details:", exc_info=True)
                
                raise
            
            # Extract data
            content = getattr(response, "output_text", None) or ""

            # Fallback: sometimes `output_text` can be empty even when output contains content
            if not content:
                extracted_chunks: List[str] = []
                try:
                    output_items = getattr(response, "output", None) or []
                    for item in output_items:
                        # item/content can be SDK objects or plain dicts depending on SDK/version
                        item_content = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)
                        for c in item_content or []:
                            if isinstance(c, dict):
                                t = c.get("text")
                                if t:
                                    extracted_chunks.append(str(t))
                                continue
                            t = getattr(c, "text", None)
                            if t:
                                extracted_chunks.append(str(t))
                    content = "\n".join(extracted_chunks).strip()
                except Exception:
                    # Non-fatal; keep content as empty string
                    content = content or ""
            
            # Extract token usage
            tokens_used = getattr(response.usage, 'total_tokens', 0) if hasattr(response, 'usage') else 0
            prompt_tokens = getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') else 0
            completion_tokens = getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') else 0
            finish_reason = getattr(response, 'finish_reason', 'completed')
            
            logger.info(f"[OpenAI API] Token usage - Total: {tokens_used}, Prompt: {prompt_tokens}, Completion: {completion_tokens}")
            logger.info(f"[OpenAI API] Finish reason: {finish_reason}")

            # Summarise output types for debugging (avoid logging raw content)
            output_summary: List[Dict[str, Any]] = []
            try:
                output_items = getattr(response, "output", None) or []
                for item in output_items:
                    if isinstance(item, dict):
                        item_type = item.get("type")
                        role = item.get("role")
                        c_list = item.get("content") or []
                        c_types = [
                            (x.get("type") if isinstance(x, dict) else getattr(x, "type", None))
                            for x in c_list
                        ]
                    else:
                        item_type = getattr(item, "type", None)
                        role = getattr(item, "role", None)
                        c_list = getattr(item, "content", None) or []
                        c_types = [getattr(x, "type", None) for x in c_list]
                    output_summary.append(
                        {
                            "type": item_type,
                            "role": role,
                            "content_types": [ct for ct in c_types if ct],
                        }
                    )
            except Exception:
                output_summary = []
            
            if not content:
                try:
                    output_len = len(getattr(response, "output", None) or [])
                except Exception:
                    output_len = None
                logger.warning(
                    "[OpenAI API] Empty content returned (output_text empty and fallback extraction found nothing). "
                    "finish_reason=%s tokens_used=%s output_items=%s response_id=%s output_summary=%s",
                    finish_reason,
                    tokens_used,
                    output_len,
                    getattr(response, "id", None),
                    output_summary,
                )

            # Return structured response
            return {
                "content": content,
                "model": model,
                "tokens_used": tokens_used,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "finish_reason": finish_reason,
                "response_id": getattr(response, "id", None),
                "output_summary": output_summary,
            }
            
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            logger.error(f"[OpenAI API] ❌❌❌ API call failed after all retries ❌❌❌")
            logger.error(f"[OpenAI API] Final error type: {error_type}")
            logger.error(f"[OpenAI API] Final error message: {error_msg}")
            logger.error(f"[OpenAI API] Full exception traceback:", exc_info=True)
            
            # Check for timeout errors
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                logger.error(f"[OpenAI API] ⏱️ Timeout error detected. Timeout setting: {settings.OPENAI_TIMEOUT} seconds")
                logger.error(f"[OpenAI API] Read timeout: {self.client.timeout.read if hasattr(self.client.timeout, 'read') else 'N/A'} seconds")
                raise Exception(f"OpenAI API request timed out after {settings.OPENAI_TIMEOUT} seconds. The request may be too complex or the server is slow. Error: {error_msg}")
            
            # Check for API key errors
            if "api key" in error_msg.lower() or "authentication" in error_msg.lower():
                logger.error("[OpenAI API] 🔑 Authentication error detected")
                raise Exception(f"OpenAI API authentication failed. Please check your OPENAI_API_KEY. Error: {error_msg}")
            
            # Check for 500 errors specifically
            if "500" in error_msg or "Internal Server Error" in error_msg:
                logger.error("[OpenAI API] ⚠️⚠️⚠️ OpenAI server returned 500 Internal Server Error after all retries ⚠️⚠️⚠️")
                logger.error(f"[OpenAI API] This indicates a temporary issue on OpenAI's side.")
                logger.error(f"[OpenAI API] All {self.client.max_retries + 1} attempts failed.")
                raise Exception(f"OpenAI API returned 500 Internal Server Error after all retries. This is likely a temporary issue on OpenAI's side. Please try again later. Error: {error_msg}")
            
            # Check for rate limiting
            if "429" in error_msg or "rate limit" in error_msg.lower():
                logger.error("[OpenAI API] ⚠️ Rate limit error after all retries")
                raise Exception(f"OpenAI API rate limit exceeded after all retries. Please wait and try again later. Error: {error_msg}")
            
            raise Exception(f"OpenAI Responses API error: {error_msg}")
    
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
        
        # Try to fix common issues:
        # 1. Add missing commas before closing braces/brackets (but not at the end)
        # 2. Remove trailing commas
        # 3. Fix unescaped newlines in strings (replace \n with \\n inside strings)
        
        # First, try to escape unescaped newlines in string values
        # This is tricky - we need to find string values and escape newlines
        # For now, let's try a simpler approach: replace literal newlines with \\n in JSON strings
        
        # Remove trailing commas before } or ]
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # Try to add missing commas between object/array items
        # This is complex, so we'll do a simple pattern match
        # Look for: } { or ] [ or } [ or ] { without comma
        content = re.sub(r'}\s*{', '},{', content)
        content = re.sub(r']\s*\[', '],[', content)
        content = re.sub(r'}\s*\[', '},[', content)
        content = re.sub(r']\s*{', '],{', content)
        
        # Try to fix missing commas after values before closing braces/brackets
        # Pattern: value } or value ] where value is not already followed by comma
        # This is very tricky, so we'll be conservative
        
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
        Generate JSON completion from OpenAI using Responses API.
        Automatically parses response as JSON.
        
        Args:
            messages: List of message objects with 'role' and 'content'
            temperature: Override default temperature
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            file_ids: Optional list of OpenAI file IDs to attach to the last user message
            
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
            model=model or settings.OPENAI_MODEL,
            max_output_tokens=max_output_tokens,
        )
        
        # Parse JSON content
        logger.info("[OpenAI] Parsing JSON response...")
        content = result["content"]
        
        # Try direct parse first
        try:
            parsed_content = json.loads(content)
            result["parsed_content"] = parsed_content
            logger.info("[OpenAI]  JSON parsed successfully (direct parse)")
            logger.info(f"[OpenAI] Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'Not a dict'}")
        except json.JSONDecodeError as e:
            logger.warning(f"[OpenAI]   Direct JSON parse failed: {str(e)}")
            logger.info("[OpenAI] Attempting to extract JSON from markdown...")
            
            # Remove markdown code blocks if present
            if "```json" in content:
                logger.info("[OpenAI] Found ```json code block, extracting...")
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                logger.info("[OpenAI] Found ``` code block, extracting...")
                content = content.split("```")[1].split("```")[0].strip()
            
            # Try parsing after markdown extraction
            try:
                parsed_content = json.loads(content)
                result["parsed_content"] = parsed_content
                logger.info("[OpenAI]  JSON parsed successfully (from markdown)")
                logger.info(f"[OpenAI] Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'Not a dict'}")
            except json.JSONDecodeError as e2:
                logger.warning(f"[OpenAI]  JSON parsing failed after markdown extraction: {str(e2)}")
                logger.info("[OpenAI] Attempting to repair JSON...")
                
                # Try to repair JSON
                try:
                    repaired_content = self._repair_json(content)
                    parsed_content = json.loads(repaired_content)
                    result["parsed_content"] = parsed_content
                    logger.info("[OpenAI]  JSON parsed successfully (after repair)")
                    logger.info(f"[OpenAI] Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'Not a dict'}")
                except (json.JSONDecodeError, Exception) as e3:
                    # Log the error location for debugging
                    error_line = None
                    error_col = None
                    if isinstance(e2, json.JSONDecodeError):
                        error_line = getattr(e2, 'lineno', None)
                        error_col = getattr(e2, 'colno', None)
                    
                    # Log content around the error
                    if error_line:
                        lines = content.split('\n')
                        start = max(0, error_line - 3)
                        end = min(len(lines), error_line + 3)
                        context = '\n'.join(lines[start:end])
                        logger.error(f"[OpenAI]  JSON repair failed: {str(e3)}")
                        logger.error(f"[OpenAI]  Error at line {error_line}, col {error_col}")
                        logger.error(f"[OpenAI]  Context around error:\n{context}")
                    else:
                        logger.error(f"[OpenAI]  JSON repair failed: {str(e3)}")
                        logger.error(f"[OpenAI]  Content preview (first 1000 chars): {content[:1000]}")
                    
                    raise Exception(f"Failed to parse JSON response after repair attempts: {str(e2)}\nError location: line {error_line}, col {error_col if error_col else 'unknown'}")
        
        return result
    
    async def generate_summary(
        self,
        system_prompt: str,
        user_responses: Dict[str, Any],
        reasoning_effort: str = "medium"
    ) -> Dict[str, Any]:
        """
        Generate a summary from user responses.
        
        Args:
            system_prompt: Developer/system prompt for the summary
            user_responses: User's diagnostic responses
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            
        Returns:
            Dictionary containing summary and metadata
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_responses)}
        ]
        
        return await self.generate_completion(
            messages=messages,
            reasoning_effort=reasoning_effort,
            model=settings.OPENAI_MODEL
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
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Process user scores using GPT with the scoring map.
        This is the core AI processing step.
        
        Args:
            scoring_prompt: Instructions for scoring (scoring_prompt.md)
            scoring_map: Mapping of questions to scores
            task_library: Library of predefined tasks
            diagnostic_questions: Full diagnostic survey structure
            user_responses: User's answers
            file_context: Context about uploaded files (Balance Sheets, P&L, etc.)
            file_ids: List of OpenAI file IDs to attach for AI analysis
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            
        Returns:
            Dictionary containing scoring results, roadmap, and advisor report
        """
        logger.info("[OpenAI] ========== Starting process_scoring ==========")

        
        # Build file context message if files are present
        file_context_msg = ""
        if file_context:
            file_context_msg = f"\n\n{file_context}"
        
        question_text_map = {}
        for page in diagnostic_questions.get("pages", []):
            for element in page.get("elements", []):
                question_text_map[element["name"]] = element.get("title", element["name"])
        

        # Build system message
        system_content = (
            f"{scoring_prompt}\n\n"
            f"Scoring Map: {json.dumps(scoring_map)}\n\n"
            f"Process User Responses using Scoring Map and store as scored_rows.\n"
            f"Join scored_rows array with roadmap array in the same json structure.\n\n"
            f"Task Library: {json.dumps(task_library)}\n\n"
            f"IMPORTANT: Respond with valid JSON only. No markdown, no explanations."
            f"{file_context_msg}"
        )
        
        # Build user message
        user_content = (
            f"Question Text Map: {json.dumps(question_text_map)}\n\n"
            f"User Responses: {json.dumps(user_responses)}\n\n"
            f"Generate a complete JSON response with scored_rows, roadmap, and advisorReport."
        )
        
        messages = [
            {
                "role": "system",
                "content": system_content
            },
            {
                "role": "user",
                "content": user_content
            }
        ]
        
        import time
        scoring_start_time = time.time()
        
        try:
            logger.info("[OpenAI] ⏳ Starting generate_json_completion (this may take several minutes)...")
            result = await self.generate_json_completion(
                messages=messages,
                temperature=0.3,
                reasoning_effort=reasoning_effort,
                file_ids=file_ids if file_ids else None,
                tools=tools
            )
            scoring_elapsed = time.time() - scoring_start_time
            logger.info(f"[OpenAI] ✅ generate_json_completion completed successfully in {scoring_elapsed:.2f} seconds ({scoring_elapsed/60:.2f} minutes)")
            return result
        except Exception as e:
            scoring_elapsed = time.time() - scoring_start_time
            error_msg = str(e)
            logger.error(f"[OpenAI] ❌ generate_json_completion failed after {scoring_elapsed:.2f} seconds ({scoring_elapsed/60:.2f} minutes)")
            logger.error(f"[OpenAI] Error: {error_msg}")
            logger.error(f"[OpenAI] Full exception details:", exc_info=True)
            raise
    
    async def generate_advice(
        self,
        advice_prompt: str,
        scoring_data: Dict[str, Any],
        reasoning_effort: str = "medium"
    ) -> Dict[str, Any]:
        """
        Generate personalized advice based on scoring results.
        
        Args:
            advice_prompt: Prompt for generating advice
            scoring_data: Complete scoring data with roadmap and advisor report
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            
        Returns:
            Dictionary containing advice and metadata
        """
        messages = [
            {"role": "system", "content": advice_prompt},
            {"role": "user", "content": json.dumps(scoring_data)}
        ]
        
        return await self.generate_completion(
            messages=messages,
            reasoning_effort=reasoning_effort,
            model=settings.OPENAI_MODEL
        )
    
    async def generate_tasks(
        self,
        task_prompt: str,
        diagnostic_summary: str,
        json_extract: Dict[str, Any],
        roadmap: List[Dict[str, Any]],
        reasoning_effort: str = "medium"
    ) -> Dict[str, Any]:
        """
        Generate tasks based on diagnostic results.
        Follows PHP implementation: uses summary, json_extract, and roadmap.
        
        Args:
            task_prompt: Prompt for task generation
            diagnostic_summary: Summary of the diagnostic
            json_extract: Q&A extract (question text → answer pairs)
            roadmap: Priority roadmap with module rankings
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            
        Returns:
            Dictionary containing generated tasks and metadata
        """
        # Build context with strict data-grounding requirements
        context = (
            f"You are an expert business advisor named 'Trinity'. "
            f"Based on the following diagnostic data, provide a JSON object with a 'tasks' array containing tasks "
            f"a business owner should action within the next 30 days.\n\n"
            f"CRITICAL RULE: Every task you generate MUST be directly supported by specific data in the "
            f"Diagnostic Data (Q&A) or the Priority Roadmap below. DO NOT generate generic business advice "
            f"or tasks that are not directly evidenced by this business's actual responses. "
            f"If a module scored Green (≥ 4.0), do NOT create tasks for it unless the Q&A reveals a specific gap. "
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
                    f"Only create tasks for Amber/Red modules — skip Green modules unless there is a clear specific gap in the Q&A. "
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
            reasoning_effort=reasoning_effort,
            model=settings.OPENAI_MODEL
        )
    
    async def upload_file(
        self,
        file_path: str,
        purpose: str = "user_data"
    ) -> Optional[Dict[str, Any]]:
        """
        Upload a file to OpenAI for analysis.
        
        Args:
            file_path: Path to the file to upload
            purpose: Purpose of the file ("user_data", "assistants", etc.)
            
        Returns:
            Dictionary with file information including 'id', or None if failed
        """
        try:
            # Verify file exists before uploading
            import os
            if not os.path.exists(file_path):
                print(f" File not found at path: {file_path}")
                raise FileNotFoundError(f"File not found: {file_path}")
            
            print(f" File found at path: {file_path}")
            
            # Run file upload in thread pool to avoid blocking
            # loop = asyncio.get_event_loop()
            
            # def upload():
            #     with open(file_path, 'rb') as file:
            #         return self.client.files.create(
            #             file=file,
            #             purpose=purpose
            #         )
            
            # response = await loop.run_in_executor(None, upload)
            
            # Read file and upload directly with async client
            with open(file_path, 'rb') as file:
                response = await self.client.files.create(
                    file=file,
                    purpose=purpose
                )
            logger.info(f"[OpenAI]  File uploaded: {response.id}")
            return {
                "id": response.id,
                "filename": response.filename,
                "bytes": response.bytes,
                "purpose": response.purpose,
                "created_at": response.created_at
            }
            
        except Exception as e:
            logger.error(f"[OpenAI]  File upload error: {str(e)}", exc_info=True)
            return None


# Singleton instance
openai_service = OpenAIService()

