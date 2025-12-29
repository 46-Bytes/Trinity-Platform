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
            logger.info(f"🔍 Checking for existing diagnostic conversation")
            existing_diagnostic = self.db.query(Diagnostic).filter(
                Diagnostic.id == diagnostic_id,
                Diagnostic.conversation_id.isnot(None)
            ).first()
            
            if existing_diagnostic and existing_diagnostic.conversation_id:
                conversation = self.db.query(Conversation).filter(
                    Conversation.id == existing_diagnostic.conversation_id
                ).first()
                if conversation:
                    logger.info(f"✅ Found existing conversation for diagnostic: {conversation.id}")
                    return conversation
        
        # For diagnostic category, try to reuse most recent diagnostic conversation
        if category == "diagnostic":
            logger.info(f"🔍 Looking for most recent diagnostic conversation for user")
            existing_diagnostic = self.db.query(Diagnostic).filter(
                Diagnostic.created_by_user_id == user_id,
                Diagnostic.conversation_id.isnot(None)
            ).order_by(Diagnostic.created_at.desc()).first()
            
            if existing_diagnostic and existing_diagnostic.conversation_id:
                conversation = self.db.query(Conversation).filter(
                    Conversation.id == existing_diagnostic.conversation_id
                ).first()
                if conversation:
                    logger.info(f"✅ Found most recent diagnostic conversation: {conversation.id}")
                    return conversation
        
        # Create new conversation
        logger.info(f"🔍 Creating new conversation")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Category: {category}")
        logger.info(f"   Diagnostic ID: {diagnostic_id}")
        
        conversation = Conversation(
            user_id=user_id,
            category=category,
            title=f"{category.title()} Chat" if category != "general" else None
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        logger.info(f"✅ Created new conversation: {conversation.id}")
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
                logger.info(f"✅ Linked diagnostic {diagnostic_id} to conversation {conversation.id}")
            else:
                logger.warning(f"⚠️ Diagnostic {diagnostic_id} not found")
        
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
        logger.info(f"Looking for conversation {conversation_id} for user {user_id}")
        
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
        engagement_id: Optional[UUID] = None
    ) -> Message:
        """
        Send a message in a conversation and get AI response.
        
        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user sending the message
            message_text: The message content
            limit: Maximum number of previous messages to include in context
            engagement_id: Optional engagement ID to find diagnostic context
            
        Returns:
            Assistant Message model with the AI response
        """
        logger.info(f"📨 STEP 1: Starting send_message for conversation {conversation_id}, user {user_id}")
        logger.info(f"   Message length: {len(message_text)} characters")
        logger.info(f"   Engagement ID: {engagement_id}")
        
        # STEP 2: Verify conversation belongs to user
        logger.info(f"📨 STEP 2: Verifying conversation ownership")
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            logger.error(f"❌ Conversation {conversation_id} not found or unauthorized for user {user_id}")
            raise ValueError(f"Conversation {conversation_id} not found or unauthorized")
        logger.info(f"✅ Conversation verified: category={conversation.category}, user_id={conversation.user_id}")
        
        # STEP 3: Save user message
        logger.info(f"📨 STEP 3: Saving user message to database")
        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            message=message_text
        )
        self.db.add(user_message)
        self.db.commit()
        self.db.refresh(user_message)
        logger.info(f"✅ User message saved: message_id={user_message.id}")
        
        # STEP 4: Get conversation history
        logger.info(f"📨 STEP 4: Retrieving conversation history (limit={limit})")
        previous_messages = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).limit(limit).all()
        logger.info(f"✅ Retrieved {len(previous_messages)} previous messages")
        
        # STEP 5: Build GPT context
        logger.info(f"📨 STEP 5: Building GPT context")
        logger.info(f"   - Conversation category: {conversation.category}")
        logger.info(f"   - Previous messages: {len(previous_messages)}")
        logger.info(f"   - Engagement ID: {engagement_id}")
        
        messages = self._build_gpt_context(
            conversation=conversation,
            previous_messages=previous_messages,
            current_message=message_text,
            engagement_id=engagement_id
        )
        
        logger.info(f"✅ GPT context built: {len(messages)} total messages")
        logger.info(f"   - System message: {len(messages[0]['content']) if messages else 0} characters")
        logger.info(f"   - Conversation history: {len(previous_messages)} messages")
        logger.info(f"   - Current message: {len(message_text)} characters")
        
        # STEP 6: Call OpenAI
        logger.info(f"📨 STEP 6: Calling OpenAI API")
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
            
            logger.info(f"✅ OpenAI response received")
            logger.info(f"   - Model: {response_data.get('model')}")
            logger.info(f"   - Response length: {len(response_text)} characters")
            logger.info(f"   - Tokens used: {response_data.get('tokens_used')}")
            logger.info(f"   - Prompt tokens: {response_data.get('prompt_tokens')}")
            logger.info(f"   - Completion tokens: {response_data.get('completion_tokens')}")
            
        except Exception as e:
            logger.error(f"❌ Error calling OpenAI: {str(e)}", exc_info=True)
            response_text = "I apologize, but I'm having trouble processing your request right now. Please try again later."
            response_data = {"error": str(e)}
        
        # STEP 7: Save assistant message
        logger.info(f"📨 STEP 7: Saving assistant message to database")
        assistant_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            message=response_text,
            response_data=response_data,
            message_metadata={"model": gpt_response.get("model", "gpt-4o-mini") if 'gpt_response' in locals() else "gpt-4o-mini"}
        )
        self.db.add(assistant_message)
        
        # STEP 8: Update conversation timestamp
        logger.info(f"📨 STEP 8: Updating conversation timestamp")
        conversation.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(assistant_message)
        logger.info(f"✅ Assistant message saved: message_id={assistant_message.id}")
        logger.info(f"✅ Conversation updated: updated_at={conversation.updated_at}")
        logger.info(f"🎉 Message processing complete!")
        
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
        logger.info(f"🔧 Building GPT context for conversation {conversation.id}")
        logger.info(f"   Category: {conversation.category}")
        logger.info(f"   Previous messages: {len(previous_messages)}")
        logger.info(f"   Engagement ID: {engagement_id}")
        
        messages = []
        
        # 1. Build system prompt
        logger.info(f"🔧 Step 1: Building system prompt")
        system_prompt = self._build_system_prompt(conversation, engagement_id=engagement_id)
        logger.info(f"   System prompt length: {len(system_prompt)} characters")
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # 2. Add conversation history
        logger.info(f"🔧 Step 2: Adding conversation history ({len(previous_messages)} messages)")
        for idx, msg in enumerate(previous_messages):
            messages.append({
                "role": msg.role,
                "content": msg.message
            })
            if idx < 3:  # Log first 3 messages for debugging
                logger.debug(f"   Message {idx + 1}: {msg.role} - {msg.message[:50]}...")
        
        # 3. Add current user message
        logger.info(f"🔧 Step 3: Adding current user message")
        messages.append({
            "role": "user",
            "content": current_message
        })
        logger.info(f"   Current message: {current_message[:100]}...")
        
        logger.info(f"✅ GPT context built: {len(messages)} total messages")
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
        logger.info(f"🔧 Building system prompt for category: {conversation.category}")
        
        # Load base system prompt
        logger.info(f"🔧 Loading base system prompt")
        try:
            base_prompt = load_prompt("system_prompt")
            logger.info(f"✅ Base system prompt loaded from file ({len(base_prompt)} characters)")
        except Exception as e:
            logger.warning(f"⚠️ Could not load system_prompt.md, using default: {str(e)}")
            base_prompt = (
                "You are Trinity, an expert business advisor. "
                "You help business owners improve their operations, financial health, and prepare for sale. "
                "Be professional, friendly, and provide actionable advice."
            )
        
        # Add user name if available
        logger.info(f"🔧 Adding user name to prompt")
        user = self.db.query(User).filter(User.id == conversation.user_id).first()
        if user and user.name:
            base_prompt += f"\n\nThe user's name is {user.name}."
            logger.info(f"✅ User name added: {user.name}")
        else:
            logger.info(f"⚠️ User name not available")
        
        # Add category-specific prompt
        logger.info(f"🔧 Loading category prompt for: {conversation.category}")
        category_prompt = self._get_category_prompt(conversation.category)
        if category_prompt:
            base_prompt += f"\n\n{category_prompt}"
            logger.info(f"✅ Category prompt added ({len(category_prompt)} characters)")
        else:
            logger.warning(f"⚠️ No category prompt found for: {conversation.category}")
        
        # Add diagnostic context for ALL categories (if diagnostic is completed)
        # This ensures all conversations have access to diagnostic data
        logger.info(f"🔧 Loading diagnostic context (engagement_id: {engagement_id})")
        diagnostic_context = self._get_diagnostic_context(conversation, engagement_id=engagement_id)
        if diagnostic_context:
            base_prompt += f"\n\n{diagnostic_context}"
            logger.info(f"✅ Diagnostic context added ({len(diagnostic_context)} characters)")
        else:
            logger.info(f"ℹ️ No diagnostic context available (diagnostic may not be completed)")
        
        logger.info(f"✅ System prompt built: total length = {len(base_prompt)} characters")
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
        logger.info(f"🔧 Getting category prompt for: {category}")
        
        try:
            # Try loading the prompt file directly
            prompt = load_prompt(f"category_prompt_{category}")
            logger.info(f"✅ Category prompt loaded from: category_prompt_{category}.md ({len(prompt)} characters)")
            return prompt
        except Exception as e:
            logger.debug(f"⚠️ Could not load category_prompt_{category}.md: {str(e)}")
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
                "diagnostic": "diagnostic",
                "diagnostics": "diagnostic",
                "general": "general",
                "competitive-forces": "competitive-forces",
                "financial-docs": "financial-docs",
                "brand-ip-intangibles": "brand-ip-intangibles",
                "brand": "brand-ip-intangibles",
                "ip": "brand-ip-intangibles",
                "intangibles": "brand-ip-intangibles",
            }
            
            normalized_category = category_variations.get(category.lower(), category.lower())
            logger.info(f"🔧 Trying normalized category: {normalized_category}")
            
            try:
                prompt = load_prompt(f"category_prompt_{normalized_category}")
                logger.info(f"✅ Category prompt loaded from: category_prompt_{normalized_category}.md ({len(prompt)} characters)")
                return prompt
            except Exception as e2:
                logger.warning(f"⚠️ Could not load category_prompt_{normalized_category}.md: {str(e2)}")
                # Fallback to default prompts if file still doesn't exist
                logger.warning(f"⚠️ Using default prompt for category: {category}")
                default_prompts = {
                    "general": "This is a general business advisory conversation. Provide helpful business advice.",
                    "diagnostic": "This conversation is about a completed business diagnostic. Reference the diagnostic findings when relevant.",
                    "financial": "This conversation focuses on financial matters. Provide financial advice and analysis.",
                    "legal-licensing": "This conversation focuses on legal and compliance matters.",
                    "operations": "This conversation focuses on business operations and processes.",
                }
                default = default_prompts.get(normalized_category)
                if default:
                    logger.info(f"✅ Using default prompt ({len(default)} characters)")
                else:
                    logger.warning(f"❌ No default prompt available for: {normalized_category}")
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
        logger.info(f"🔧 Getting diagnostic context (engagement_id: {engagement_id})")
        diagnostic = None
        
        # First, try to find diagnostic linked to this conversation
        logger.info(f"🔧 Step 1: Looking for diagnostic linked to conversation {conversation.id}")
        diagnostic = self.db.query(Diagnostic).filter(
            Diagnostic.conversation_id == conversation.id,
            Diagnostic.status == "completed"
        ).order_by(Diagnostic.completed_at.desc()).first()
        
        if diagnostic:
            logger.info(f"✅ Found diagnostic linked to conversation: {diagnostic.id}")
        else:
            logger.info(f"ℹ️ No diagnostic linked to conversation")
        
        # If not found and engagement_id provided, find by engagement
        if not diagnostic and engagement_id:
            logger.info(f"🔧 Step 2: Looking for diagnostic by engagement_id: {engagement_id}")
            diagnostic = self.db.query(Diagnostic).filter(
                Diagnostic.engagement_id == engagement_id,
                Diagnostic.status == "completed"
            ).order_by(Diagnostic.completed_at.desc()).first()
            
            if diagnostic:
                logger.info(f"✅ Found diagnostic by engagement: {diagnostic.id}")
            else:
                logger.info(f"ℹ️ No diagnostic found for engagement")
        
        # If still not found, try to find any completed diagnostic for this user
        if not diagnostic:
            logger.info(f"🔧 Step 3: Looking for any completed diagnostic for user {conversation.user_id}")
            diagnostic = self.db.query(Diagnostic).filter(
                Diagnostic.created_by_user_id == conversation.user_id,
                Diagnostic.status == "completed"
            ).order_by(Diagnostic.completed_at.desc()).first()
            
            if diagnostic:
                logger.info(f"✅ Found user's most recent diagnostic: {diagnostic.id}")
            else:
                logger.info(f"ℹ️ No completed diagnostic found for user")
        
        if not diagnostic:
            logger.info(f"❌ No diagnostic context available")
            return None
        
        logger.info(f"✅ Diagnostic found: {diagnostic.id}, building context")
        context_parts = []
        
        # Add diagnostic summary
        logger.info(f"🔧 Extracting diagnostic summary")
        if diagnostic.ai_analysis and isinstance(diagnostic.ai_analysis, dict):
            summary = diagnostic.ai_analysis.get("summary", "")
            if summary:
                context_parts.append(f"Diagnostic Summary:\n{summary}")
                logger.info(f"✅ Summary added ({len(summary)} characters)")
            else:
                logger.warning(f"⚠️ No summary in ai_analysis")
        else:
            logger.warning(f"⚠️ ai_analysis is not a dict or missing")
        
        # Add diagnostic advice
        logger.info(f"🔧 Extracting diagnostic advice")
        if diagnostic.ai_analysis and isinstance(diagnostic.ai_analysis, dict):
            advice = diagnostic.ai_analysis.get("advisorReport", "")
            if advice:
                context_parts.append(f"Diagnostic Advice:\n{advice}")
                logger.info(f"✅ Advice added ({len(advice)} characters)")
            else:
                logger.warning(f"⚠️ No advisorReport in ai_analysis")
        
        # Add Q&A extract if available (from user_responses)
        logger.info(f"🔧 Extracting Q&A data")
        if diagnostic.user_responses:
            qa_json = json.dumps(diagnostic.user_responses, indent=2)
            context_parts.append(f"Diagnostic Q&A Data:\n{qa_json}")
            logger.info(f"✅ Q&A data added ({len(qa_json)} characters)")
        else:
            logger.warning(f"⚠️ No user_responses available")
        
        if context_parts:
            context = (
                "Use the following information from the user's completed diagnostic to respond. "
                "Remind the user about significant information and events from their diagnostic.\n\n"
                + "\n\n".join(context_parts)
            )
            logger.info(f"✅ Diagnostic context built: {len(context)} total characters")
            logger.info(f"   - Parts included: {len(context_parts)}")
            return context
        
        logger.warning(f"⚠️ No context parts available, returning None")
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

