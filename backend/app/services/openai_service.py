"""
OpenAI service for GPT interactions using Responses API
"""
from typing import Dict, Any, List, Optional
import json
from openai import OpenAI
from app.config import settings


class OpenAIService:
    """Service for interacting with OpenAI Responses API"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.temperature = settings.OPENAI_TEMPERATURE
    
    def _convert_messages_to_input(
        self, 
        messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Convert chat completion messages to Responses API input format.
        Changes 'system' role to 'developer' role.
        
        Args:
            messages: List of message objects with 'role' and 'content'
            
        Returns:
            List of input messages with converted roles
        """
        input_messages = []
        for msg in messages:
            role = msg["role"]
            # Convert 'system' role to 'developer' for Responses API
            if role == "system":
                role = "developer"
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
        reasoning_effort: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate completion from OpenAI using Responses API.
        
        Args:
            messages: List of message objects with 'role' and 'content'
                     ('system' role will be converted to 'developer')
            temperature: Override default temperature
            json_mode: Enable JSON mode output
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            
        Returns:
            Dictionary containing response and metadata
        """
        try:
            # Convert messages to input format
            input_messages = self._convert_messages_to_input(messages)
            
            # Prepare parameters
            params = {
                "model": self.model,
                "input": input_messages,
            }
            
            # Add temperature if specified
            if temperature is not None:
                params["temperature"] = temperature
            else:
                params["temperature"] = self.temperature
            
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
        reasoning_effort: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate JSON completion from OpenAI using Responses API.
        Automatically parses response as JSON.
        
        Args:
            messages: List of message objects with 'role' and 'content'
            temperature: Override default temperature
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            
        Returns:
            Dictionary containing parsed JSON response and metadata
        """
        result = await self.generate_completion(
            messages=messages,
            temperature=temperature,
            json_mode=True,
            reasoning_effort=reasoning_effort
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
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            
        Returns:
            Dictionary containing scoring results, roadmap, and advisor report
        """
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
                )
            },
            {
                "role": "user",
                "content": (
                    f"Diagnostic: {json.dumps(diagnostic_questions)}\n\n"
                    f"User Responses: {json.dumps(user_responses)}\n\n"
                    f"Generate a complete JSON response with scored_rows, roadmap, and advisorReport."
                )
            }
        ]
        
        return await self.generate_json_completion(
            messages=messages,
            reasoning_effort=reasoning_effort
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
            f'"description": "Task description with step-by-step instructions", '
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


# Singleton instance
openai_service = OpenAIService()

