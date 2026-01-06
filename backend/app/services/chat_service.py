"""
Chat service for managing conversations and messages with Trinity AI
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime
import json
import logging
import time

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
        
        Args:
            user_id: UUID of the user
            category: Conversation category (general, finance, etc.)
            diagnostic_id: Optional diagnostic ID to link to conversation
            
        Returns:
            Conversation model
        """
        
        conversation = Conversation(
            user_id=user_id,
            category=category,
            title=f"{category.title()} Chat" if category != "general" else None
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        logger.info(f"  Created new conversation: {conversation.id}")
        logger.info(f"   Title: {conversation.title}")
        
        # Link diagnostic to conversation if provided
        if diagnostic_id:
            logger.info(f"🔍 Linking diagnostic {diagnostic_id} to conversation {conversation.id}")
            diagnostic = self.db.query(Diagnostic).filter(
                Diagnostic.id == diagnostic_id
            ).first()
            if diagnostic:
                diagnostic.conversation_id = conversation.id
                self.db.commit()
                logger.info(f"  Linked diagnostic {diagnostic_id} to conversation {conversation.id}")
            else:
                logger.warning(f"  Diagnostic {diagnostic_id} not found")
        
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
        
        # First check if conversation exists at all
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            logger.warning(f"Conversation {conversation_id} not found in database")
            return None
        
        # Then check if it belongs to the user
        if conversation.user_id != user_id:
            logger.warning(f"Conversation {conversation_id} belongs to user {conversation.user_id}, but requested by user {user_id}")
            return None
        
        logger.info(f"Found conversation {conversation_id} for user {user_id}")
        return conversation
    
    # ==================== MESSAGE MANAGEMENT ====================
    
    async def send_message(
        self,
        conversation_id: UUID,
        user_id: UUID,
        message_text: str,
        limit: int = 50,
        engagement_id: Optional[UUID] = None,
        model: str = "gpt-5.1"
    ) -> Message:
        """
        Send a message in a conversation and get AI response.
        
        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user sending the message
            message_text: The message content
            limit: Maximum number of previous messages to include in context
            engagement_id: Optional engagement ID to find diagnostic context
            model: Model to use for the response
        Returns:
            Assistant Message model with the AI response
        """
        t0 = time.time()
        conversation = self.get_conversation(conversation_id, user_id)
        t1 = time.time()
        logger.info(f"[TIMESTAMP] send_message start: {t0:.3f}s | After get_conversation: {t1:.3f}s | Elapsed: {t1-t0:.3f}s")
        
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found or unauthorized")
        
        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            message=message_text
        )

        t1a = time.time()
        self.db.add(user_message)
        t1b = time.time()
        self.db.commit()
        t1c = time.time()
        self.db.refresh(user_message)
        t2 = time.time()
        logger.info(f"[TIMESTAMP] After save user message - add: {t1b:.3f}s | commit: {t1c:.3f}s | refresh: {t2:.3f}s | Total: {t2-t1:.3f}s")
        
        previous_messages = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).limit(limit).all()
        t3 = time.time()
        logger.info(f"[TIMESTAMP] After get history: {t3:.3f}s | Elapsed: {t3-t2:.3f}s")
        
        messages = self._build_gpt_context(
            conversation=conversation,
            previous_messages=previous_messages,
            current_message=message_text,
            engagement_id=engagement_id
        )
        t4 = time.time()
        logger.info(f"[TIMESTAMP] After build context: {t4:.3f}s | Elapsed: {t4-t3:.3f}s")
        
        try:
            t5 = time.time()
            gpt_response = await openai_service.generate_completion(
                messages=messages,
                temperature=0.7,
                model=model,
                max_output_tokens=1000,
            )
            t6 = time.time()
            logger.info(f"[TIMESTAMP] Before OpenAI: {t5:.3f}s | After OpenAI: {t6:.3f}s | OpenAI elapsed: {t6-t5:.3f}s")
            
            response_text = gpt_response.get("content", "")
            response_data = {
                "model": gpt_response.get("model"),
                "tokens_used": gpt_response.get("tokens_used", 0),
                "prompt_tokens": gpt_response.get("prompt_tokens", 0),
                "completion_tokens": gpt_response.get("completion_tokens", 0),
            }
            
        except Exception as e:
            logger.error(f"  Error calling OpenAI: {str(e)}", exc_info=True)
            response_text = "I apologize, but I'm having trouble processing your request right now. Please try again later."
            response_data = {"error": str(e)}
        
        assistant_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            message=response_text,
            response_data=response_data,
            message_metadata={"model": gpt_response.get("model", "gpt-4o-mini") if 'gpt_response' in locals() else "gpt-4o-mini"}
        )
        t6a = time.time()
        self.db.add(assistant_message)
        t6b = time.time()
        conversation.updated_at = datetime.utcnow()
        t6c = time.time()
        self.db.commit()
        t6d = time.time()
        self.db.refresh(assistant_message)
        t7 = time.time()
        logger.info(f"[TIMESTAMP] After save assistant - add: {t6b:.3f}s | update: {t6c:.3f}s | commit: {t6d:.3f}s | refresh: {t7:.3f}s | Total: {t7-t6:.3f}s | Grand Total: {t7-t0:.3f}s")
        
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
        current_message: str,
        engagement_id: Optional[UUID] = None
    ) -> List[Dict[str, str]]:
        """
        Build the GPT message context for a chat turn.
        Includes system prompt, category prompt, diagnostic context, and conversation history.
        
        Args:
            conversation: Conversation model
            previous_messages: List of previous Message models
            current_message: Current user message text
            engagement_id: Optional engagement ID to find diagnostic
            
        Returns:
            List of message dicts for OpenAI API
        """
        t0 = time.time()
        messages = []
        
        # 1. Build system prompt
        system_prompt = self._build_system_prompt(conversation, engagement_id=engagement_id)
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        t1 = time.time()
        logger.info(f"[TIMESTAMP] _build_gpt_context - After system prompt: {t1:.3f}s | Elapsed: {t1-t0:.3f}s")
        
        # 2. Add conversation history
        for idx, msg in enumerate(previous_messages):
            messages.append({
                "role": msg.role,
                "content": msg.message
            })
        t2 = time.time()
        logger.info(f"[TIMESTAMP] _build_gpt_context - After add history: {t2:.3f}s | Elapsed: {t2-t1:.3f}s")
        
        # 3. Add current user message
        messages.append({
            "role": "user",
            "content": current_message
        })
        t3 = time.time()
        logger.info(f"[TIMESTAMP] _build_gpt_context - Complete: {t3:.3f}s | Total: {t3-t0:.3f}s")
        return messages
    
    def _build_system_prompt(self, conversation: Conversation, engagement_id: Optional[UUID] = None) -> str:
        """
        Build the system prompt for a conversation.
        Includes base prompt, category prompt, and diagnostic context if available.
        
        Args:
            conversation: Conversation model
            engagement_id: Optional engagement ID to find diagnostic
            
        Returns:
            System prompt string
        """
        t0 = time.time()
        try:
            base_prompt = load_prompt("system_prompt")
        except Exception as e:
            logger.warning(f"  Could not load system_prompt.md, using default: {str(e)}")
            base_prompt = (
                "You are Trinity, an expert business advisor. "
                "You help business owners improve their operations, financial health, and prepare for sale. "
                "Be professional, friendly, and provide actionable advice."
            )
        t1 = time.time()
        logger.info(f"[TIMESTAMP] After load base prompt: {t1:.3f}s | Elapsed: {t1-t0:.3f}s")
        
        # Add user name if available
        t1a = time.time()
        user = self.db.query(User).filter(User.id == conversation.user_id).first()
        t1b = time.time()
        logger.info(f"[TIMESTAMP] _build_system_prompt - User query: {t1b:.3f}s | Elapsed: {t1b-t1a:.3f}s")
        if user and user.name:
            base_prompt += f"\n\nThe user's name is {user.name}."
        
        # Add category-specific prompt
        category_prompt = self._get_category_prompt(conversation.category)
        if category_prompt:
            base_prompt += f"\n\n{category_prompt}"
        t2 = time.time()
        logger.info(f"[TIMESTAMP] After category prompt: {t2:.3f}s | Elapsed: {t2-t1:.3f}s")
        
        diagnostic_context = self._get_diagnostic_context(conversation, engagement_id=engagement_id)
        if diagnostic_context:
            base_prompt += f"\n\n{diagnostic_context}"
        t3 = time.time()
        logger.info(f"[TIMESTAMP] After diagnostic context: {t3:.3f}s | Elapsed: {t3-t2:.3f}s | Total: {t3-t0:.3f}s")
        return base_prompt
    
    def _get_category_prompt(self, category: str) -> Optional[str]:
        """
        Get category-specific prompt from prompt files.
        Handles category names with hyphens (e.g., "legal-licensing" -> "category_prompt_legal-licensing.md")
        
        Args:
            category: Conversation category
            
        Returns:
            Category prompt string or None
        """
        t0 = time.time()
        try:
            # Try loading the prompt file directly
            prompt = load_prompt(f"category_prompt_{category}")
            t1 = time.time()
            logger.info(f"[TIMESTAMP] _get_category_prompt - Loaded {category}: {t1:.3f}s | Elapsed: {t1-t0:.3f}s")
            return prompt
        except Exception as e:
            logger.debug(f"  Could not load category_prompt_{category}.md: {str(e)}")
            # If file doesn't exist, try alternative names
            # Handle common variations
            category_variations = {
                "financial": "financial",
                "finance": "financial",
                "legal": "legal-licensing",
                "legal-licensing": "legal-licensing",
                "operations": "operations",
                "ops": "operations",
                "human-resources": "human-resources",
                "hr": "human-resources",
                "people": "human-resources",
                "customers": "customers",
                "customer": "customers",
                "tax": "tax",
                "due-diligence": "due-diligence",
                "dd": "due-diligence",
                "general": "general",
                "brand-ip-intangibles": "brand-ip-intangibles",
                "brand": "brand-ip-intangibles",
                "ip": "brand-ip-intangibles",
                "intangibles": "brand-ip-intangibles",
            }
            
            normalized_category = category_variations.get(category.lower(), category.lower())
            
            try:
                prompt = load_prompt(f"category_prompt_{normalized_category}")
                t2 = time.time()
                logger.info(f"[TIMESTAMP] _get_category_prompt - Loaded normalized {normalized_category}: {t2:.3f}s | Elapsed: {t2-t0:.3f}s")
                return prompt
            except Exception as e2:
                logger.warning(f"  Could not load category_prompt_{normalized_category}.md: {str(e2)}")
                # Fallback to default prompts if file still doesn't exist
                logger.warning(f"  Using default prompt for category: {category}")
                default_prompts = {
                    "general": "This is a general business advisory conversation. Provide helpful business advice.",
                    "financial": "This conversation focuses on financial matters. Provide financial advice and analysis.",
                    "legal-licensing": "This conversation focuses on legal and compliance matters.",
                    "operations": "This conversation focuses on business operations and processes.",
                }
                default = default_prompts.get(normalized_category)
                t3 = time.time()
                logger.info(f"[TIMESTAMP] _get_category_prompt - Using default: {t3:.3f}s | Elapsed: {t3-t0:.3f}s")
                if default:
                    logger.info(f"  Using default prompt ({len(default)} characters)")
                else:
                    logger.warning(f"  No default prompt available for: {normalized_category}")
                return default
    
    def _get_diagnostic_context(self, conversation: Conversation, engagement_id: Optional[UUID] = None) -> Optional[str]:
        """
        Get diagnostic context for a conversation.
        For ALL categories, includes diagnostic data if available.
        First tries to find diagnostic linked to conversation, then falls back to engagement.
        
        Args:
            conversation: Conversation model
            engagement_id: Optional engagement ID to find diagnostic by engagement
            
        Returns:
            Diagnostic context string or None
        """
        t0 = time.time()
        diagnostic = None
        
        # First, try to find diagnostic linked to this conversation
        t1 = time.time()
        diagnostic = self.db.query(Diagnostic).filter(
            Diagnostic.conversation_id == conversation.id,
            Diagnostic.status == "completed"
        ).order_by(Diagnostic.completed_at.desc()).first()
        t2 = time.time()
        logger.info(f"[TIMESTAMP] _get_diagnostic_context - Query by conversation_id: {t2:.3f}s | Elapsed: {t2-t1:.3f}s")
        
        if not diagnostic and engagement_id:
            t3 = time.time()
            diagnostic = self.db.query(Diagnostic).filter(
                Diagnostic.engagement_id == engagement_id,
                Diagnostic.status == "completed"
            ).order_by(Diagnostic.completed_at.desc()).first()
            t4 = time.time()
            logger.info(f"[TIMESTAMP] _get_diagnostic_context - Query by engagement_id: {t4:.3f}s | Elapsed: {t4-t3:.3f}s")
        
        # If still not found, try to find any completed diagnostic for this user
        if not diagnostic:
            t5 = time.time()
            diagnostic = self.db.query(Diagnostic).filter(
                Diagnostic.created_by_user_id == conversation.user_id,
                Diagnostic.status == "completed"
            ).order_by(Diagnostic.completed_at.desc()).first()
            t6 = time.time()
            logger.info(f"[TIMESTAMP] _get_diagnostic_context - Query by user_id: {t6:.3f}s | Elapsed: {t6-t5:.3f}s")
            
            if diagnostic:
                return None
        
        if not diagnostic:
            t7 = time.time()
            logger.info(f"[TIMESTAMP] _get_diagnostic_context - No diagnostic found: {t7:.3f}s | Total: {t7-t0:.3f}s")
            return None
        
        context_parts = []
        t8 = time.time()
        
        # Add diagnostic summary
        if diagnostic.ai_analysis and isinstance(diagnostic.ai_analysis, dict):
            summary = diagnostic.ai_analysis.get("summary", "")
            if summary:
                context_parts.append(f"Diagnostic Summary:\n{summary}")
        
            advice = diagnostic.ai_analysis.get("advisorReport", "")
            if advice:
                # Truncate advice to first 2000 characters if too long
                advice_truncated = advice[:2000] + "..." if len(advice) > 2000 else advice
                context_parts.append(f"Diagnostic Advice:\n{advice_truncated}")
        
        t9 = time.time()
        logger.info(f"[TIMESTAMP] _get_diagnostic_context - After extract context: {t9:.3f}s | Elapsed: {t9-t8:.3f}s")
        
        if context_parts:
            context = (
                "Use the following information from the user's completed diagnostic to respond. "
                "Remind the user about significant information and events from their diagnostic.\n\n"
                + "\n\n".join(context_parts)
            )
            t10 = time.time()
            logger.info(f"[TIMESTAMP] _get_diagnostic_context - Complete: {t10:.3f}s | Total: {t10-t0:.3f}s")
            return context
        
        t11 = time.time()
        logger.info(f"[TIMESTAMP] _get_diagnostic_context - No context parts: {t11:.3f}s | Total: {t11-t0:.3f}s")
        return None
    
    async def _generate_welcome_message(self, category: str) -> Optional[str]:
        """
        Generate a welcome message for a new conversation.
        This version is fully static (no LLM call) to avoid latency and cost.
        
        Args:
            category: Conversation category
            
        Returns:
            Welcome message string or None
        """
        # Normalize category names similar to _get_category_prompt
        normalized = (category or "").lower()
        category_variations = {
            "financial": "financial",
            "finance": "financial",
            "legal": "legal-licensing",
            "legal-licensing": "legal-licensing",
            "operations": "operations",
            "ops": "operations",
            "human-resources": "human-resources",
            "hr": "human-resources",
            "people": "human-resources",
            "customers": "customers",
            "customer": "customers",
            "tax": "tax",
            "due-diligence": "due-diligence",
            "dd": "due-diligence",
            "brand-ip-intangibles": "brand-ip-intangibles",
            "brand": "brand-ip-intangibles",
            "ip": "brand-ip-intangibles",
            "intangibles": "brand-ip-intangibles",
            "general": "general",
        }
        normalized = category_variations.get(normalized, normalized or "general")

        welcome_messages = {
            "general": "Hello! I'm Trinity, your business advisor. How can I help you today?",
            "financial": "Hello! I'm Trinity, and I'm here to help with your financial questions. What would you like to discuss?",
            "legal-licensing": "Hello! I'm Trinity, and I'm here to help with legal, licensing, and compliance matters. What would you like to discuss?",
            "operations": "Hello! I'm Trinity, and I'm here to help with your business operations. What would you like to discuss?",
            "human-resources": "Hello! I'm Trinity, and I'm here to help with your team and HR questions. What would you like to discuss?",
            "customers": "Hello! I'm Trinity, and I'm here to help with your customers, sales, and retention. What would you like to discuss?",
            "tax": "Hello! I'm Trinity, and I'm here to help with tax and related planning questions. What would you like to discuss?",
            "due-diligence": "Hello! I'm Trinity, and I'm here to help you think through due diligence and preparation. What would you like to discuss?",
            "brand-ip-intangibles": "Hello! I'm Trinity, and I'm here to help with your brand, IP, and other intangibles. What would you like to discuss?",
            "diagnostic": "Hello! I'm Trinity. I can help you interpret your diagnostic results and next steps. What would you like to focus on first?",
        }

        return welcome_messages.get(
            normalized,
            "Hello! I'm Trinity, your business advisor. How can I help you today?",
        )
    
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

