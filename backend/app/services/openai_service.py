"""
OpenAI service — COMMENTED OUT (Anthropic Claude is now the active LLM provider).
To switch back to OpenAI:
  1. Uncomment the OpenAI implementation below
  2. Comment out the Anthropic re-export at the bottom
  3. Update config.py and .env to use OPENAI_* settings
  4. Replace 'anthropic' with 'openai' in requirements.txt
"""

# ============================================================
# OPENAI IMPLEMENTATION (commented out — switch back by uncommenting)
# ============================================================

# from typing import Dict, Any, List, Optional
# import json
# import os
#
# import time
# import asyncio
# from openai import AsyncOpenAI
# from app.config import settings
# import logging
# import httpx
# logger = logging.getLogger(__name__)
# import time
#
#
# class OpenAIService:
#     """Service for interacting with OpenAI Responses API"""
#
#     # Class-level client that will be initialized once at startup
#     _client: Optional[AsyncOpenAI] = None
#
#     def __init__(self):
#         """Initialize OpenAI service (client is initialized separately at startup)"""
#         self.temperature = settings.OPENAI_TEMPERATURE
#
#     @classmethod
#     def initialize_client(cls):
#         """Initialize the OpenAI client once at application startup"""
#         if cls._client is None:
#             cls._client = AsyncOpenAI(
#                 api_key=settings.OPENAI_API_KEY,
#                 timeout=httpx.Timeout(
#                     connect=10.0,
#                     read=1800.0,
#                     write=10.0,
#                     pool=10.0
#                 ),
#                 max_retries=2
#             )
#             if settings.OPENAI_TIMEOUT is not None:
#                 timeout_str = f"{settings.OPENAI_TIMEOUT} seconds ({settings.OPENAI_TIMEOUT/60:.1f} minutes)"
#             else:
#                 timeout_str = "no timeout"
#             logger.info(f"OpenAI client initialized with timeout: {timeout_str}")
#         return cls._client
#
#     @property
#     def client(self) -> AsyncOpenAI:
#         """Get the shared OpenAI client instance"""
#         if OpenAIService._client is None:
#             raise RuntimeError(
#                 "OpenAI client not initialized. Call OpenAIService.initialize_client() "
#                 "at application startup (e.g., in main.py startup event)."
#             )
#         return OpenAIService._client
#
#     def _convert_messages_to_input(
#         self,
#         messages: List[Dict[str, str]],
#         file_ids: Optional[List[str]] = None
#     ) -> List[Dict[str, Any]]:
#         """
#         Convert chat completion messages to Responses API input format.
#         Changes 'system' role to 'developer' role.
#         Supports file attachments in the last user message.
#         """
#         input_messages = []
#
#         for idx, msg in enumerate(messages):
#             role = msg["role"]
#             if role == "system":
#                 role = "developer"
#
#             is_last_user_message = (
#                 idx == len(messages) - 1 and
#                 msg["role"] == "user" and
#                 file_ids and
#                 len(file_ids) > 0
#             )
#
#             if is_last_user_message:
#                 content_array = []
#                 for file_id in file_ids:
#                     content_array.append({
#                         "type": "input_file",
#                         "file_id": file_id
#                     })
#                 content_array.append({
#                     "type": "input_text",
#                     "text": msg["content"]
#                 })
#                 input_messages.append({
#                     "role": role,
#                     "content": content_array
#                 })
#             else:
#                 input_messages.append({
#                     "role": role,
#                     "content": msg["content"]
#                 })
#
#         return input_messages
#
#     async def generate_completion(
#         self,
#         messages: List[Dict[str, str]],
#         temperature: Optional[float] = None,
#         json_mode: bool = False,
#         reasoning_effort: Optional[str] = None,
#         file_ids: Optional[List[str]] = None,
#         tools: Optional[List[Dict[str, Any]]] = None,
#         model: str = "gpt-5-nano",
#         max_output_tokens: Optional[int] = None,
#     ) -> Dict[str, Any]:
#         """Generate completion from OpenAI using Responses API."""
#         try:
#             input_messages = self._convert_messages_to_input(messages, file_ids=file_ids)
#             logger.info(f"GPT Model: {model}")
#
#             params = {
#                 "model": model,
#                 "input": input_messages,
#                 "max_output_tokens": max_output_tokens,
#             }
#
#             if json_mode:
#                 params["text"] = {"format": {"type": "json_object"}}
#
#             if reasoning_effort:
#                 params["reasoning"] = {"effort": reasoning_effort}
#
#             if tools:
#                 normalized_tools: List[Dict[str, Any]] = []
#                 for t in tools:
#                     if not isinstance(t, dict):
#                         continue
#                     if t.get("type") == "code_interpreter" and "container" not in t:
#                         normalized_tools.append({**t, "container": {"type": "auto"}})
#                     else:
#                         normalized_tools.append(t)
#                 params["tools"] = normalized_tools
#
#             start_time = time.time()
#             try:
#                 logger.info("[OpenAI API] Making API call to OpenAI Responses API...")
#                 response = await self.client.responses.create(**params)
#                 elapsed_time = time.time() - start_time
#                 logger.info(f"[OpenAI API] API call succeeded in {elapsed_time:.2f} seconds")
#             except Exception as executor_error:
#                 elapsed_time = time.time() - start_time
#                 error_msg = str(executor_error)
#                 error_type = type(executor_error).__name__
#                 logger.error(f"[OpenAI API] API call failed after {elapsed_time:.2f} seconds")
#                 logger.error(f"[OpenAI API] Error type: {error_type}")
#                 logger.error(f"[OpenAI API] Error message: {error_msg}")
#                 if elapsed_time >= 600:
#                     logger.error(f"[OpenAI API] Request took {elapsed_time:.2f} seconds - likely a timeout")
#                 status_code = None
#                 if hasattr(executor_error, 'status_code'):
#                     status_code = executor_error.status_code
#                 elif hasattr(executor_error, 'response'):
#                     if hasattr(executor_error.response, 'status_code'):
#                         status_code = executor_error.response.status_code
#                 if status_code:
#                     logger.error(f"[OpenAI API] HTTP Status Code: {status_code}")
#                 logger.error(f"[OpenAI API] Full exception details:", exc_info=True)
#                 raise
#
#             content = getattr(response, "output_text", None) or ""
#             if not content:
#                 extracted_chunks: List[str] = []
#                 try:
#                     output_items = getattr(response, "output", None) or []
#                     for item in output_items:
#                         item_content = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)
#                         for c in item_content or []:
#                             if isinstance(c, dict):
#                                 t = c.get("text")
#                                 if t:
#                                     extracted_chunks.append(str(t))
#                                 continue
#                             t = getattr(c, "text", None)
#                             if t:
#                                 extracted_chunks.append(str(t))
#                     content = "\n".join(extracted_chunks).strip()
#                 except Exception:
#                     content = content or ""
#
#             if not content:
#                 ci_chunks: List[str] = []
#                 try:
#                     output_items = getattr(response, "output", None) or []
#                     for item in output_items:
#                         item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
#                         if item_type != "code_interpreter_call":
#                             continue
#                         results = item.get("results") if isinstance(item, dict) else getattr(item, "results", None)
#                         for r in results or []:
#                             r_type = r.get("type") if isinstance(r, dict) else getattr(r, "type", None)
#                             if r_type == "logs":
#                                 logs = r.get("logs") if isinstance(r, dict) else getattr(r, "logs", None)
#                                 if logs and str(logs).strip():
#                                     ci_chunks.append(str(logs))
#                     if ci_chunks:
#                         content = "\n".join(ci_chunks).strip()
#                         logger.info(f"[OpenAI API] Recovered content from code_interpreter logs ({len(ci_chunks)} chunks)")
#                 except Exception:
#                     pass
#
#             tokens_used = getattr(response.usage, 'total_tokens', 0) if hasattr(response, 'usage') else 0
#             prompt_tokens = getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') else 0
#             completion_tokens = getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') else 0
#             finish_reason = getattr(response, 'finish_reason', 'completed')
#
#             logger.info(f"[OpenAI API] Token usage - Total: {tokens_used}, Prompt: {prompt_tokens}, Completion: {completion_tokens}")
#             logger.info(f"[OpenAI API] Finish reason: {finish_reason}")
#
#             output_summary: List[Dict[str, Any]] = []
#             try:
#                 output_items = getattr(response, "output", None) or []
#                 for item in output_items:
#                     if isinstance(item, dict):
#                         item_type = item.get("type")
#                         role = item.get("role")
#                         c_list = item.get("content") or []
#                         c_types = [(x.get("type") if isinstance(x, dict) else getattr(x, "type", None)) for x in c_list]
#                     else:
#                         item_type = getattr(item, "type", None)
#                         role = getattr(item, "role", None)
#                         c_list = getattr(item, "content", None) or []
#                         c_types = [getattr(x, "type", None) for x in c_list]
#                     summary_entry: Dict[str, Any] = {"type": item_type, "role": role, "content_types": [ct for ct in c_types if ct]}
#                     if item_type == "code_interpreter_call":
#                         results = item.get("results") if isinstance(item, dict) else getattr(item, "results", None)
#                         if results:
#                             result_types = [r.get("type") if isinstance(r, dict) else getattr(r, "type", None) for r in results]
#                             summary_entry["result_types"] = result_types
#                             summary_entry["result_count"] = len(results)
#                         else:
#                             summary_entry["result_count"] = 0
#                     output_summary.append(summary_entry)
#             except Exception:
#                 output_summary = []
#
#             if not content:
#                 logger.warning("[OpenAI API] Empty content returned")
#
#             return {
#                 "content": content,
#                 "model": model,
#                 "tokens_used": tokens_used,
#                 "prompt_tokens": prompt_tokens,
#                 "completion_tokens": completion_tokens,
#                 "finish_reason": finish_reason,
#                 "response_id": getattr(response, "id", None),
#                 "output_summary": output_summary,
#             }
#
#         except Exception as e:
#             error_msg = str(e)
#             error_type = type(e).__name__
#             logger.error(f"[OpenAI API] API call failed after all retries")
#             logger.error(f"[OpenAI API] Final error: {error_msg}")
#             logger.error(f"[OpenAI API] Full exception traceback:", exc_info=True)
#             if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
#                 raise Exception(f"OpenAI API request timed out. Error: {error_msg}")
#             if "api key" in error_msg.lower() or "authentication" in error_msg.lower():
#                 raise Exception(f"OpenAI API authentication failed. Error: {error_msg}")
#             if "500" in error_msg or "Internal Server Error" in error_msg:
#                 raise Exception(f"OpenAI API returned 500 after all retries. Error: {error_msg}")
#             if "429" in error_msg or "rate limit" in error_msg.lower():
#                 raise Exception(f"OpenAI API rate limit exceeded. Error: {error_msg}")
#             raise Exception(f"OpenAI Responses API error: {error_msg}")
#
#     def _repair_json(self, content: str) -> str:
#         """Attempt to repair common JSON syntax errors."""
#         import re
#         if "```json" in content:
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif "```" in content:
#             content = content.split("```")[1].split("```")[0].strip()
#         content = re.sub(r',(\s*[}\]])', r'\1', content)
#         content = re.sub(r'}\s*{', '},{', content)
#         content = re.sub(r']\s*\[', '],[', content)
#         content = re.sub(r'}\s*\[', '},[', content)
#         content = re.sub(r']\s*{', '],{', content)
#         return content.strip()
#
#     async def generate_json_completion(
#         self,
#         messages: List[Dict[str, str]],
#         temperature: Optional[float] = None,
#         reasoning_effort: Optional[str] = None,
#         file_ids: Optional[List[str]] = None,
#         tools: Optional[List[Dict[str, Any]]] = None,
#         model: Optional[str] = None,
#         max_output_tokens: Optional[int] = None,
#     ) -> Dict[str, Any]:
#         """Generate JSON completion from OpenAI using Responses API."""
#         result = await self.generate_completion(
#             messages=messages, temperature=temperature, json_mode=True,
#             reasoning_effort=reasoning_effort, file_ids=file_ids, tools=tools,
#             model=model or settings.OPENAI_MODEL, max_output_tokens=max_output_tokens,
#         )
#         logger.info("[OpenAI] Parsing JSON response...")
#         content = result["content"]
#         try:
#             parsed_content = json.loads(content)
#             result["parsed_content"] = parsed_content
#             logger.info("[OpenAI] JSON parsed successfully (direct parse)")
#         except json.JSONDecodeError as e:
#             logger.warning(f"[OpenAI] Direct JSON parse failed: {str(e)}")
#             if "```json" in content:
#                 content = content.split("```json")[1].split("```")[0].strip()
#             elif "```" in content:
#                 content = content.split("```")[1].split("```")[0].strip()
#             try:
#                 parsed_content = json.loads(content)
#                 result["parsed_content"] = parsed_content
#             except json.JSONDecodeError as e2:
#                 try:
#                     repaired_content = self._repair_json(content)
#                     parsed_content = json.loads(repaired_content)
#                     result["parsed_content"] = parsed_content
#                 except (json.JSONDecodeError, Exception) as e3:
#                     raise Exception(f"Failed to parse JSON response: {str(e2)}")
#         return result
#
#     async def generate_summary(self, system_prompt, user_responses, reasoning_effort="medium"):
#         messages = [
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": json.dumps(user_responses)}
#         ]
#         return await self.generate_completion(messages=messages, reasoning_effort=reasoning_effort, model=settings.OPENAI_MODEL)
#
#     async def process_scoring(self, scoring_prompt, scoring_map, task_library, diagnostic_questions,
#                               user_responses, file_context=None, file_ids=None, reasoning_effort="low", tools=None):
#         logger.info("[OpenAI] ========== Starting process_scoring ==========")
#         file_context_msg = f"\n\n{file_context}" if file_context else ""
#         question_text_map = {}
#         for page in diagnostic_questions.get("pages", []):
#             for element in page.get("elements", []):
#                 question_text_map[element["name"]] = element.get("title", element["name"])
#         system_content = (f"{scoring_prompt}\n\nScoring Map: {json.dumps(scoring_map)}\n\n"
#                          f"Process User Responses using Scoring Map and store as scored_rows.\n"
#                          f"Join scored_rows array with roadmap array in the same json structure.\n\n"
#                          f"Task Library: {json.dumps(task_library)}\n\n"
#                          f"IMPORTANT: Respond with valid JSON only. No markdown, no explanations.{file_context_msg}")
#         user_content = (f"Question Text Map: {json.dumps(question_text_map)}\n\n"
#                        f"User Responses: {json.dumps(user_responses)}\n\n"
#                        f"Generate a complete JSON response with scored_rows, roadmap, and advisorReport.")
#         messages = [{"role": "system", "content": system_content}, {"role": "user", "content": user_content}]
#         return await self.generate_json_completion(messages=messages, temperature=0.3,
#                                                    reasoning_effort=reasoning_effort,
#                                                    file_ids=file_ids if file_ids else None, tools=tools)
#
#     async def generate_advice(self, advice_prompt, scoring_data, reasoning_effort="medium"):
#         messages = [
#             {"role": "system", "content": advice_prompt},
#             {"role": "user", "content": json.dumps(scoring_data)}
#         ]
#         return await self.generate_completion(messages=messages, reasoning_effort=reasoning_effort, model=settings.OPENAI_MODEL)
#
#     async def generate_tasks(self, task_prompt, diagnostic_summary, json_extract, roadmap, reasoning_effort="medium"):
#         context = (f"You are an expert business advisor named 'Trinity'. "
#                   f"Based on the following diagnostic data, provide a JSON object with a 'tasks' array...\n\n"
#                   f"Summary: {diagnostic_summary}\n\n"
#                   f"Diagnostic Data (Q&A): {json.dumps(json_extract)}\n\n"
#                   f"Priority Roadmap:\n{json.dumps(roadmap, indent=2)}\n\n{task_prompt}")
#         messages = [{"role": "system", "content": context},
#                    {"role": "user", "content": "Generate actionable tasks in JSON format. Return ONLY the JSON object."}]
#         return await self.generate_json_completion(messages=messages, reasoning_effort=reasoning_effort, model=settings.OPENAI_MODEL)
#
#     async def upload_file(self, file_path, purpose="user_data"):
#         try:
#             if not os.path.exists(file_path):
#                 raise FileNotFoundError(f"File not found: {file_path}")
#             with open(file_path, 'rb') as file:
#                 response = await self.client.files.create(file=file, purpose=purpose)
#             logger.info(f"[OpenAI] File uploaded: {response.id}")
#             return {"id": response.id, "filename": response.filename, "bytes": response.bytes,
#                     "purpose": response.purpose, "created_at": response.created_at}
#         except Exception as e:
#             logger.error(f"[OpenAI] File upload error: {str(e)}", exc_info=True)
#             return None
#
#
# # Singleton instance (OpenAI)
# # openai_service = OpenAIService()


# ============================================================
# ACTIVE LLM SERVICE: Anthropic Claude
# To switch back to OpenAI: uncomment the class above, comment out the lines below
# ============================================================
from app.services.anthropic_service import AnthropicService, anthropic_service

# Re-export Anthropic service under OpenAI names for backward compatibility
# Consumer files that import `from app.services.openai_service import openai_service`
# will get the Anthropic service without needing import changes.
OpenAIService = AnthropicService
openai_service = anthropic_service
