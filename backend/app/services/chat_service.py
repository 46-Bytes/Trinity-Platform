"""
Chat service for managing conversations and messages with Trinity AI
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime
import json
import logging

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.diagnostic import Diagnostic
from app.models.user import User
from app.services.openai_service import openai_service
from app.utils.file_loader import load_prompt

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for managing chat conversations with Trinity AI.
    Handles conversation creation, message sending, and context building.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== CONVERSATION MANAGEMENT ====================
    
    def get_or_create_conversation(
        self,
        user_id: UUID,
        category: str = "general",
        diagnostic_id: Optional[UUID] = None
    ) -> Conversation:
        """
        Get or create a conversation for a user.
        
        If diagnostic_id is provided, links the conversation to that diagnostic.
        For diagnostic category, reuses existing diagnostic conversation if available.
        
        Args:
            user_id: UUID of the user
            category: Conversation category (general, diagnostic, finance, etc.)
            diagnostic_id: Optional diagnostic ID to link to conversation
            
        Returns:
            Conversation model
        """
        # For diagnostic category, check if there's an existing conversation for this diagnostic
        if category == "diagnostic" and diagnostic_id:
            existing_diagnostic = self.db.query(Diagnostic).filter(
                Diagnostic.id == diagnostic_id,
                Diagnostic.conversation_id.isnot(None)
            ).first()
            
            if existing_diagnostic and existing_diagnostic.conversation_id:
                conversation = self.db.query(Conversation).filter(
                    Conversation.id == existing_diagnostic.conversation_id
                ).first()
                if conversation:
                    return conversation
        
        # For diagnostic category, try to reuse most recent diagnostic conversation
        if category == "diagnostic":
            existing_diagnostic = self.db.query(Diagnostic).filter(
                Diagnostic.created_by_user_id == user_id,
                Diagnostic.conversation_id.isnot(None)
            ).order_by(Diagnostic.created_at.desc()).first()
            
            if existing_diagnostic and existing_diagnostic.conversation_id:
                conversation = self.db.query(Conversation).filter(
                    Conversation.id == existing_diagnostic.conversation_id
                ).first()
                if conversation:
                    return conversation
        
        # Create new conversation
        conversation = Conversation(
            user_id=user_id,
            category=category,
            title=f"{category.title()} Chat" if category != "general" else None
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        # Link diagnostic to conversation if provided
        if diagnostic_id:
            diagnostic = self.db.query(Diagnostic).filter(
                Diagnostic.id == diagnostic_id
            ).first()
            if diagnostic:
                diagnostic.conversation_id = conversation.id
                self.db.commit()
        
        # For non-diagnostic categories, create a welcome message
        # Note: Welcome message creation is skipped for now to avoid async complexity
        # Can be added later if needed
        
        return conversation
    
    def get_user_conversations(self, user_id: UUID) -> List[Conversation]:
        """
        Get all conversations for a user, ordered by most recent activity.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            List of Conversation models
        """
        conversations = self.db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(Conversation.updated_at.desc()).all()
        
        return conversations
    
    def get_conversation(self, conversation_id: UUID, user_id: UUID) -> Optional[Conversation]:
        """
        Get a specific conversation by ID, ensuring it belongs to the user.
        
        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user (for authorization)
            
        Returns:
            Conversation model or None if not found/unauthorized
        """
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        return conversation
    
    # ==================== MESSAGE MANAGEMENT ====================
    
    async def send_message(
        self,
        conversation_id: UUID,
        user_id: UUID,
        message_text: str,
        limit: int = 50
    ) -> Message:
        """
        Send a message in a conversation and get AI response.
        
        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user sending the message
            message_text: The message content
            limit: Maximum number of previous messages to include in context
            
        Returns:
            Assistant Message model with the AI response
        """
        # Verify conversation belongs to user
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found or unauthorized")
        
        # Save user message
        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            message=message_text
        )
        self.db.add(user_message)
        self.db.commit()
        self.db.refresh(user_message)
        
        # Get conversation history
        previous_messages = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).limit(limit).all()
        
        # Build GPT context
        messages = self._build_gpt_context(
            conversation=conversation,
            previous_messages=previous_messages,
            current_message=message_text
        )
        
        # Call OpenAI
        try:
            gpt_response = await openai_service.generate_completion(
                messages=messages,
                temperature=0.7
            )
            
            response_text = gpt_response.get("content", "")
            response_data = {
                "model": gpt_response.get("model"),
                "tokens_used": gpt_response.get("tokens_used", 0),
                "prompt_tokens": gpt_response.get("prompt_tokens", 0),
                "completion_tokens": gpt_response.get("completion_tokens", 0),
            }
            
        except Exception as e:
            logger.error(f"Error calling OpenAI: {str(e)}")
            response_text = "I apologize, but I'm having trouble processing your request right now. Please try again later."
            response_data = {"error": str(e)}
        
        # Save assistant message
        assistant_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            message=response_text,
            response_data=response_data,
            message_metadata={"model": gpt_response.get("model", "gpt-4o")}
        )
        self.db.add(assistant_message)
        
        # Update conversation timestamp
        conversation.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(assistant_message)
        
        return assistant_message
    
    def get_conversation_messages(
        self,
        conversation_id: UUID,
        user_id: UUID,
        limit: Optional[int] = None
    ) -> List[Message]:
        """
        Get messages for a conversation.
        
        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user (for authorization)
            limit: Optional limit on number of messages
            
        Returns:
            List of Message models
        """
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            return []
        
        query = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    # ==================== GPT CONTEXT BUILDING ====================
    
    def _build_gpt_context(
        self,
        conversation: Conversation,
        previous_messages: List[Message],
        current_message: str
    ) -> List[Dict[str, str]]:
        """
        Build the GPT message context for a chat turn.
        Includes system prompt, category prompt, diagnostic context, and conversation history.
        
        Args:
            conversation: Conversation model
            previous_messages: List of previous Message models
            current_message: Current user message text
            
        Returns:
            List of message dicts for OpenAI API
        """
        messages = []
        
        # 1. Build system prompt
        system_prompt = self._build_system_prompt(conversation)
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # 2. Add conversation history
        for msg in previous_messages:
            messages.append({
                "role": msg.role,
                "content": msg.message
            })
        
        # 3. Add current user message
        messages.append({
            "role": "user",
            "content": current_message
        })
        
        return messages
    
    def _build_system_prompt(self, conversation: Conversation) -> str:
        """
        Build the system prompt for a conversation.
        Includes base prompt, category prompt, and diagnostic context if available.
        
        Args:
            conversation: Conversation model
            
        Returns:
            System prompt string
        """
        # Load base system prompt
        try:
            base_prompt = load_prompt("system_prompt")
        except:
            base_prompt = (
                "You are Trinity, an expert business advisor. "
                "You help business owners improve their operations, financial health, and prepare for sale. "
                "Be professional, friendly, and provide actionable advice."
            )
        
        # Add user name if available
        user = self.db.query(User).filter(User.id == conversation.user_id).first()
        if user and user.name:
            base_prompt += f"\n\nThe user's name is {user.name}."
        
        # Add category-specific prompt
        category_prompt = self._get_category_prompt(conversation.category)
        if category_prompt:
            base_prompt += f"\n\n{category_prompt}"
        
        # Add diagnostic context if this is a diagnostic conversation
        diagnostic_context = self._get_diagnostic_context(conversation)
        if diagnostic_context:
            base_prompt += f"\n\n{diagnostic_context}"
        
        return base_prompt
    
    def _get_category_prompt(self, category: str) -> Optional[str]:
        """
        Get category-specific prompt.
        
        Args:
            category: Conversation category
            
        Returns:
            Category prompt string or None
        """
        try:
            return load_prompt(f"category_prompt_{category}")
        except:
            # Default category prompts
            category_prompts = {
                "general": "This is a general business advisory conversation. Provide helpful business advice.",
                "diagnostic": "This conversation is about a completed business diagnostic. Reference the diagnostic findings when relevant.",
                "finance": "This conversation focuses on financial matters. Provide financial advice and analysis.",
                "legal": "This conversation focuses on legal and compliance matters.",
                "operations": "This conversation focuses on business operations and processes.",
            }
            return category_prompts.get(category.lower())
    
    def _get_diagnostic_context(self, conversation: Conversation) -> Optional[str]:
        """
        Get diagnostic context for a conversation.
        If the conversation is linked to a completed diagnostic, include its data.
        
        Args:
            conversation: Conversation model
            
        Returns:
            Diagnostic context string or None
        """
        # Find diagnostic linked to this conversation
        diagnostic = self.db.query(Diagnostic).filter(
            Diagnostic.conversation_id == conversation.id,
            Diagnostic.status == "completed"
        ).order_by(Diagnostic.completed_at.desc()).first()
        
        if not diagnostic:
            return None
        
        context_parts = []
        
        # Add diagnostic summary
        if diagnostic.ai_analysis and isinstance(diagnostic.ai_analysis, dict):
            summary = diagnostic.ai_analysis.get("summary", "")
            if summary:
                context_parts.append(f"Diagnostic Summary:\n{summary}")
        
        # Add diagnostic advice
        if diagnostic.ai_analysis and isinstance(diagnostic.ai_analysis, dict):
            advice = diagnostic.ai_analysis.get("advisorReport", "")
            if advice:
                context_parts.append(f"Diagnostic Advice:\n{advice}")
        
        # Add Q&A extract if available (from user_responses)
        if diagnostic.user_responses:
            context_parts.append(f"Diagnostic Q&A Data:\n{json.dumps(diagnostic.user_responses, indent=2)}")
        
        if context_parts:
            return (
                "Use the following information from the user's completed diagnostic to respond. "
                "Remind the user about significant information and events from their diagnostic.\n\n"
                + "\n\n".join(context_parts)
            )
        
        return None
    
    async def _generate_welcome_message(self, category: str) -> Optional[str]:
        """
        Generate a welcome message for a new conversation.
        
        Args:
            category: Conversation category
            
        Returns:
            Welcome message string or None
        """
        try:
            # Try to load category-specific welcome prompt
            welcome_prompt = load_prompt(f"welcome_prompt_{category}")
            result = await openai_service.generate_completion(
                messages=[{
                    "role": "system",
                    "content": welcome_prompt
                }, {
                    "role": "user",
                    "content": ""
                }],
                temperature=0.7
            )
            return result.get("content", "")
        except:
            # Default welcome messages
            welcome_messages = {
                "general": "Hello! I'm Trinity, your business advisor. How can I help you today?",
                "finance": "Hello! I'm Trinity, and I'm here to help with your financial questions. What would you like to discuss?",
                "legal": "Hello! I'm Trinity, and I'm here to help with legal and compliance matters. What would you like to discuss?",
                "operations": "Hello! I'm Trinity, and I'm here to help with your business operations. What would you like to discuss?",
            }
            return welcome_messages.get(category.lower(), "Hello! I'm Trinity, your business advisor. How can I help you today?")
    
    # ==================== TASK/NOTE CREATION FROM MESSAGES ====================
    
    def create_task_from_message(
        self,
        message_id: UUID,
        engagement_id: UUID,
        created_by_user_id: UUID
    ) -> int:
        """
        Create a task from an assistant message.
        Uses GPT to extract task information from the message.
        
        Args:
            message_id: UUID of the assistant message
            engagement_id: UUID of the engagement to create task in
            created_by_user_id: UUID of the user creating the task
            
        Returns:
            Number of tasks created
        """
        message = self.db.query(Message).filter(
            Message.id == message_id,
            Message.role == "assistant"
        ).first()
        
        if not message:
            raise ValueError(f"Assistant message {message_id} not found")
        
        # Use GPT to extract task from message
        # This would call a task extraction prompt
        # For now, create a simple task from the message
        from app.models.task import Task
        
        task = Task(
            engagement_id=engagement_id,
            created_by_user_id=created_by_user_id,
            title=f"Task from chat: {message.message[:100]}...",
            description=message.message,
            task_type="chat_generated",
            status="pending",
            priority="medium"
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        return 1
    
    def create_note_from_message(
        self,
        message_id: UUID,
        engagement_id: UUID,
        created_by_user_id: UUID
    ) -> int:
        """
        Create a note from an assistant message.
        
        Args:
            message_id: UUID of the assistant message
            engagement_id: UUID of the engagement to create note in
            created_by_user_id: UUID of the user creating the note
            
        Returns:
            Number of notes created
        """
        message = self.db.query(Message).filter(
            Message.id == message_id,
            Message.role == "assistant"
        ).first()
        
        if not message:
            raise ValueError(f"Assistant message {message_id} not found")
        
        from app.models.note import Note
        
        note = Note(
            engagement_id=engagement_id,
            created_by_user_id=created_by_user_id,
            content=message.message,
            note_type="chat_generated"
        )
        
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        
        return 1


def get_chat_service(db: Session) -> ChatService:
    """Factory function to create ChatService with DB session."""
    return ChatService(db)

