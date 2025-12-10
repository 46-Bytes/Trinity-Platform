"""
OpenAI service for GPT interactions
"""
from typing import Dict, Any, List, Optional
import json
import openai
from app.config import settings


class OpenAIService:
    """Service for interacting with OpenAI API"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        openai.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.temperature = settings.OPENAI_TEMPERATURE
        self.max_tokens = settings.OPENAI_MAX_TOKENS
    
    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Generate completion from OpenAI.
        
        Args:
            messages: List of message objects with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens
            response_format: Response format (e.g., {"type": "json_object"})
            
        Returns:
            Dictionary containing response and metadata
        """
        try:
            # Prepare parameters
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self.temperature,
                "max_tokens": max_tokens if max_tokens is not None else self.max_tokens
            }
            
            # Add response format if specified
            if response_format:
                params["response_format"] = response_format
            
            # Make API call
            response = await openai.ChatCompletion.acreate(**params)
            
            # Extract data
            content = response.choices[0].message.content
            
            # Return structured response
            return {
                "content": content,
                "model": response.model,
                "tokens_used": response.usage.total_tokens,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "finish_reason": response.choices[0].finish_reason
            }
            
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    async def generate_json_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate JSON completion from OpenAI.
        Automatically parses response as JSON.
        
        Args:
            messages: List of message objects with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            Dictionary containing parsed JSON response and metadata
        """
        result = await self.generate_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
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
        user_responses: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a summary from user responses.
        
        Args:
            system_prompt: System prompt for the summary
            user_responses: User's diagnostic responses
            
        Returns:
            Dictionary containing summary and metadata
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_responses)}
        ]
        
        return await self.generate_completion(messages)
    
    async def process_scoring(
        self,
        scoring_prompt: str,
        scoring_map: Dict[str, Any],
        task_library: Dict[str, Any],
        diagnostic_questions: Dict[str, Any],
        user_responses: Dict[str, Any]
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
                    f"Task Library: {json.dumps(task_library)}"
                )
            },
            {
                "role": "system",
                "content": (
                    "When responding with json, respond using pure json. "
                    "When responding with html, respond using pure html. "
                    "No comments or explanations, or markdown."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Diagnostic: {json.dumps(diagnostic_questions)}\n\n"
                    f"User Responses: {json.dumps(user_responses)}"
                )
            },
            {
                "role": "user",
                "content": "Strip all markdown from the response. Leave only the json."
            }
        ]
        
        return await self.generate_json_completion(messages)
    
    async def generate_advice(
        self,
        advice_prompt: str,
        scoring_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate personalized advice based on scoring results.
        
        Args:
            advice_prompt: Prompt for generating advice
            scoring_data: Complete scoring data with roadmap and advisor report
            
        Returns:
            Dictionary containing advice and metadata
        """
        messages = [
            {"role": "system", "content": advice_prompt},
            {"role": "user", "content": json.dumps(scoring_data)}
        ]
        
        return await self.generate_completion(messages)
    
    async def generate_tasks(
        self,
        task_prompt: str,
        diagnostic_summary: str,
        user_responses: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate tasks based on diagnostic results.
        
        Args:
            task_prompt: Prompt for task generation
            diagnostic_summary: Summary of the diagnostic
            user_responses: User's diagnostic responses
            
        Returns:
            Dictionary containing generated tasks and metadata
        """
        full_prompt = (
            f"{task_prompt}\n\n"
            f"Summary: {diagnostic_summary}\n\n"
            f"User Responses: {json.dumps(user_responses)}"
        )
        
        messages = [
            {"role": "system", "content": full_prompt}
        ]
        
        return await self.generate_json_completion(messages)


# Singleton instance
openai_service = OpenAIService()

