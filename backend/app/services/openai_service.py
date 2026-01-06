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


class OpenAIService:
    """Service for interacting with OpenAI Responses API"""
    
    def __init__(self):
        """Initialize OpenAI client with configurable timeout"""
        # Set timeout (default: 3600 seconds = 1 hour for long-running processes)
        self.client = AsyncOpenAI(  # ← Changed from OpenAI to AsyncOpenAI
            api_key=settings.OPENAI_API_KEY,
            timeout=httpx.Timeout(
                connect=10.0,
                read=1800.0,      # ← 30 minutes for long requests
                write=10.0,
                pool=10.0
            ),
            max_retries=2
        )
        self.temperature = settings.OPENAI_TEMPERATURE
        # Safely format timeout string (handle None case)
        if settings.OPENAI_TIMEOUT is not None:
            timeout_str = f"{settings.OPENAI_TIMEOUT} seconds ({settings.OPENAI_TIMEOUT/60:.1f} minutes)"
        else:
            timeout_str = "no timeout"
        logger.info(f"OpenAI client initialized with timeout: {timeout_str}")
    
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
        model: str = "gpt-5.1",
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
            
            # Note: OpenAI Responses API does not support temperature parameter
            # Temperature is not included in the API call
            
            # Add JSON mode if specified
            if json_mode:
                params["text"] = {"format": {"type": "json_object"}}
            
            # Add reasoning effort if specified
            if reasoning_effort:
                params["reasoning"] = {"effort": reasoning_effort}

            # Add tools if specified (e.g., code_interpreter for CSV/text processing)
            if tools:
                # Some tool types (e.g., code_interpreter) require a container field in newer Responses API versions.
                normalized_tools: List[Dict[str, Any]] = []
                for t in tools:
                    if not isinstance(t, dict):
                        continue
                    if t.get("type") == "code_interpreter" and "container" not in t:
                        normalized_tools.append({**t, "container": {"type": "auto"}})
                    else:
                        normalized_tools.append(t)
                params["tools"] = normalized_tools
            
            t0 = time.time()
            logger.info(f"[TIMESTAMP] OpenAI API call start: {t0:.3f}s")
            
            try:
                response = await self.client.responses.create(**params)
            except Exception as executor_error:
                t_error = time.time()
                elapsed_time = t_error - t0
                logger.info(f"[TIMESTAMP] OpenAI API error: {t_error:.3f}s | Elapsed: {elapsed_time:.3f}s")
                error_msg = str(executor_error)
                raise
            
            t1 = time.time()
            elapsed_time = t1 - t0
            logger.info(f"[TIMESTAMP] OpenAI API complete: {t1:.3f}s | Elapsed: {elapsed_time:.3f}s")    
            # Extract data
            content = response.output_text
            
            # Extract token usage
            tokens_used = getattr(response.usage, 'total_tokens', 0) if hasattr(response, 'usage') else 0
            prompt_tokens = getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') else 0
            completion_tokens = getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') else 0
            finish_reason = getattr(response, 'finish_reason', 'completed')
            
            logger.info(f"[OpenAI API] Token usage - Total: {tokens_used}, Prompt: {prompt_tokens}, Completion: {completion_tokens}")
            logger.info(f"[OpenAI API] Finish reason: {finish_reason}")
            
            # Return structured response
            return {
                "content": content,
                "model": model,
                "tokens_used": tokens_used,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "finish_reason": finish_reason
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[OpenAI API]  API call failed: {error_msg}", exc_info=True)
            
            # Check for timeout errors
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                logger.error(f"[OpenAI API] Timeout error detected. Timeout setting: {settings.OPENAI_TIMEOUT} seconds")
                raise Exception(f"OpenAI API request timed out after {settings.OPENAI_TIMEOUT} seconds. The request may be too complex or the server is slow. Error: {error_msg}")
            
            # Check for API key errors
            if "api key" in error_msg.lower() or "authentication" in error_msg.lower():
                logger.error("[OpenAI API] Authentication error detected")
                raise Exception(f"OpenAI API authentication failed. Please check your OPENAI_API_KEY. Error: {error_msg}")
            
            raise Exception(f"OpenAI Responses API error: {error_msg}")
    
    async def generate_json_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        reasoning_effort: Optional[str] = None,
        file_ids: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None
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
            model=settings.OPENAI_MODEL
        )
        
        # Parse JSON content
        logger.info("[OpenAI] Parsing JSON response...")
        try:
            # Try to parse as JSON
            parsed_content = json.loads(result["content"])
            result["parsed_content"] = parsed_content
            logger.info("[OpenAI]  JSON parsed successfully (direct parse)")
            logger.info(f"[OpenAI] Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'Not a dict'}")
        except json.JSONDecodeError as e:
            logger.warning(f"[OpenAI]   Direct JSON parse failed: {str(e)}")
            logger.info("[OpenAI] Attempting to extract JSON from markdown...")
            
            # If JSON parsing fails, try to extract JSON from markdown
            content = result["content"]
            
            # Remove markdown code blocks if present
            if "```json" in content:
                logger.info("[OpenAI] Found ```json code block, extracting...")
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                logger.info("[OpenAI] Found ``` code block, extracting...")
                content = content.split("```")[1].split("```")[0].strip()
            
            try:
                parsed_content = json.loads(content)
                result["parsed_content"] = parsed_content
                logger.info("[OpenAI]  JSON parsed successfully (from markdown)")
                logger.info(f"[OpenAI] Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'Not a dict'}")
            except json.JSONDecodeError as e2:
                logger.error(f"[OpenAI]  JSON parsing failed after markdown extraction: {str(e2)}")
                logger.error(f"[OpenAI] Content preview (first 500 chars): {content[:500]}")
                raise Exception(f"Failed to parse JSON response: {str(e2)}\nContent preview: {content[:500]}...")
        
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
        reasoning_effort: str = "medium",
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
        logger.info(f"[OpenAI] File IDs provided: {len(file_ids) if file_ids else 0}")
        if file_ids:
            logger.info(f"[OpenAI] File IDs: {file_ids}")
        logger.info(f"[OpenAI] File context length: {len(file_context) if file_context else 0} characters")
        logger.info(f"[OpenAI] User responses count: {len(user_responses)}")

        
        # Build file context message if files are present
        file_context_msg = ""
        if file_context:
            file_context_msg = f"\n\n{file_context}"
            logger.info(f"[OpenAI] File context added to prompt: {len(file_context_msg)} characters")
        
        question_text_map = {}
        for page in diagnostic_questions.get("pages", []):
            for element in page.get("elements", []):
                question_text_map[element["name"]] = element.get("title", element["name"])
        
        logger.info(f"[OpenAI] Question text map built: {len(question_text_map)} questions")

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
        
        logger.info(f"[OpenAI] System message length: {len(system_content)} characters")
        logger.info(f"[OpenAI] User message length: {len(user_content)} characters")
        logger.info(f"[OpenAI] Total prompt size: ~{len(system_content) + len(user_content)} characters")
        
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
        
        logger.info("[OpenAI] Calling generate_json_completion for scoring...")
        logger.info(f"[OpenAI] Timeout setting: {self.client.timeout} seconds")
        
        try:
            result = await self.generate_json_completion(
                messages=messages,
                reasoning_effort=reasoning_effort,
                file_ids=file_ids if file_ids else None,
                tools=tools
            )
            logger.info("[OpenAI]  generate_json_completion completed successfully")
            return result
        except Exception as e:
            logger.error(f"[OpenAI]  generate_json_completion failed: {str(e)}", exc_info=True)
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
        # Build context similar to PHP implementation
        context = (
            f"You are an expert business advisor named 'Trinity'. "
            f"Based on the following diagnostic data, provide a JSON object with a 'tasks' array containing tasks "
            f"a business owner should action within the next 30 days.\n\n"
            f"Summary: {diagnostic_summary}\n\n"
            f"Diagnostic Data (Q&A): {json.dumps(json_extract)}\n\n"
            f"Priority Roadmap (Modules by Priority):\n{json.dumps(roadmap, indent=2)}\n\n"
            f"Focus on the highest priority modules (lowest rank = highest priority).\n\n"
            f"Template: {{\"tasks\": [{{"
            f'"title": "Task Title", '
            f'"description": "Task description with step-by-step instructions. Every step must be in a new line with 1. 2. 3. Numbering", '
            f'"category": "general|legal-licensing|financial|operations|human-resources|customers|competitive-forces|due-diligence|tax", '
            f'"priority": "low|medium|high|critical"'
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
                    f"Generate MULTIPLE actionable tasks in JSON format (minimum 5-10 tasks, ideally 8-12 tasks). "
                    f"Focus on the priority modules from the roadmap. "
                    f"Generate at least 1-2 tasks for each of the top 3-5 priority modules. "
                    f"Cover different categories to ensure comprehensive coverage. "
                    f"Provide detailed descriptions with step-by-step instructions for each task. "
                    f"CRITICAL: Return a JSON OBJECT with a 'tasks' key containing an array of task objects. "
                    f"Format: {{\"tasks\": [{{task1}}, {{task2}}, {{task3}}, ...]}} with at least 5-10 tasks. "
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

