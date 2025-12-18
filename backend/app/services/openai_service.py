"""
OpenAI service for GPT interactions using Responses API
"""
from typing import Dict, Any, List, Optional
import json
from openai import OpenAI
from app.config import settings
import logging
logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI Responses API"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.temperature = settings.OPENAI_TEMPERATURE
    
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
        file_ids: Optional[List[str]] = None
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
            
        Returns:
            Dictionary containing response and metadata
        """
        try:
            # Convert messages to input format (with files if provided)
            input_messages = self._convert_messages_to_input(messages, file_ids=file_ids)
            
            # Prepare parameters
            params = {
                "model": self.model,
                "input": input_messages,
            }
            
            # Note: OpenAI Responses API does not support temperature parameter
            # Temperature is not included in the API call
            
            # Add JSON mode if specified
            if json_mode:
                params["text"] = {"format": {"type": "json_object"}}
            
            # Add reasoning effort if specified
            if reasoning_effort:
                params["reasoning"] = {"effort": reasoning_effort}
            
            # Make API call using Responses API
            response = self.client.responses.create(**params)
            
            # Extract data
            content = response.output_text
            
            # Return structured response
            return {
                "content": content,
                "model": self.model,
                "tokens_used": getattr(response.usage, 'total_tokens', 0) if hasattr(response, 'usage') else 0,
                "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') else 0,
                "completion_tokens": getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') else 0,
                "finish_reason": getattr(response, 'finish_reason', 'completed')
            }
            
        except Exception as e:
            raise Exception(f"OpenAI Responses API error: {str(e)}")
    
    async def generate_json_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        reasoning_effort: Optional[str] = None,
        file_ids: Optional[List[str]] = None
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
            file_ids=file_ids
        )
        
        # Parse JSON content
        try:
            # Try to parse as JSON
            parsed_content = json.loads(result["content"])
            result["parsed_content"] = parsed_content
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract JSON from markdown
            content = result["content"]
            
            # Remove markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            try:
                parsed_content = json.loads(content)
                result["parsed_content"] = parsed_content
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON response: {str(e)}\nContent: {content}")
        
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
            reasoning_effort=reasoning_effort
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
        reasoning_effort: str = "high"
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
        # Build file context message if files are present
        file_context_msg = ""
        if file_context:
            file_context_msg = f"\n\n{file_context}"
        
        question_text_map = {}
        for page in diagnostic_questions.get("pages", []):
            for element in page.get("elements", []):
                question_text_map[element["name"]] = element.get("title", element["name"])

        messages = [
            {
                "role": "system",
                "content": (
                    f"{scoring_prompt}\n\n"
                    f"Scoring Map: {json.dumps(scoring_map)}\n\n"
                    f"Process User Responses using Scoring Map and store as scored_rows.\n"
                    f"Join scored_rows array with roadmap array in the same json structure.\n\n"
                    f"Task Library: {json.dumps(task_library)}\n\n"
                    f"IMPORTANT: Respond with valid JSON only. No markdown, no explanations."
                    f"{file_context_msg}"
                )
            },
            {
                "role": "user",
                "content": (
                    f"Question Text Map: {json.dumps(question_text_map)}\n\n"
                    f"User Responses: {json.dumps(user_responses)}\n\n"
                    f"Generate a complete JSON response with scored_rows, roadmap, and advisorReport."
                )
            }
        ]
        logger.info(f"Messages: {messages}")
        # Pass file IDs to be attached to the user message
        return await self.generate_json_completion(
            messages=messages,
            reasoning_effort=reasoning_effort,
            file_ids=file_ids if file_ids else None
        )
    
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
            reasoning_effort=reasoning_effort
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
            f"Based on the following diagnostic data, provide a JSON list of tasks "
            f"a business owner should action within the next 30 days.\n\n"
            f"Summary: {diagnostic_summary}\n\n"
            f"Diagnostic Data (Q&A): {json.dumps(json_extract)}\n\n"
            f"Priority Roadmap (Modules by Priority):\n{json.dumps(roadmap, indent=2)}\n\n"
            f"Focus on the highest priority modules (lowest rank = highest priority).\n\n"
            f"Template: [{{"
            f'"title": "Task Title", '
            f'"description": "Task description with step-by-step instructions. Ever step must be in a new line with 1. 2. 3. Numbering", '
            f'"category": "general|legal-licensing|financial|operations|human-resources|customers|competitive-forces|due-diligence|tax", '
            f'"priority": "low|medium|high|critical"'
            f"}}]\n\n"
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
                    f"Generate actionable tasks in JSON format. "
                    f"Focus on the priority modules from the roadmap. "
                    f"Provide detailed descriptions with step-by-step instructions. "
                    f"Return ONLY the JSON array, no markdown."
                )
            }
        ]
        
        return await self.generate_json_completion(
            messages=messages,
            reasoning_effort=reasoning_effort
        )
    
    async def upload_file(
        self,
        file_path: str,
        purpose: str = "assistants"
    ) -> Optional[Dict[str, Any]]:
        """
        Upload a file to OpenAI for analysis.
        
        Args:
            file_path: Path to the file to upload
            purpose: Purpose of the file ("assistants", "vision", etc.)
            
        Returns:
            Dictionary with file information including 'id', or None if failed
        """
        try:
            with open(file_path, 'rb') as file:
                response = self.client.files.create(
                    file=file,
                    purpose=purpose
                )
            
            return {
                "id": response.id,
                "filename": response.filename,
                "bytes": response.bytes,
                "purpose": response.purpose,
                "created_at": response.created_at
            }
            
        except Exception as e:
            print(f"❌ OpenAI file upload error: {str(e)}")
            return None


# Singleton instance
openai_service = OpenAIService()

