"""
Chat API endpoints for Trinity AI conversations
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ..database import get_db
from ..models.user import User
from ..schemas.chat import (
    ConversationResponse,
    ConversationCreate,
    MessageResponse,
    MessageCreate,
    ConversationListResponse
)
from ..services.chat_service import get_chat_service
from ..services.role_check import get_current_user_from_token

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Get all conversations for the current user.
    
    Returns:
        List of conversations ordered by most recent activity
    """
    chat_service = get_chat_service(db)
    conversations = chat_service.get_user_conversations(current_user.id)
    
    # Build response manually to avoid model_validate issues
    return {
        "conversations": [
            {
                "id": str(conv.id),
                "user_id": str(conv.user_id),
                "category": conv.category,
                "title": conv.title,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }
            for conv in conversations
        ]
    }


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Create a new conversation.
    
    Args:
        conversation_data: Conversation creation data (category, optional diagnostic_id)
        
    Returns:
        Created conversation
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🚀 API: Creating/getting conversation")

    
    chat_service = get_chat_service(db)
    
    conversation = chat_service.get_or_create_conversation(
        user_id=current_user.id,
        category=conversation_data.category,
        diagnostic_id=conversation_data.diagnostic_id
    )
    
    logger.info(f"✅ API: Conversation created/retrieved: {conversation.id}")
    
    # Build response manually to avoid model_validate issues
    return {
        "id": str(conversation.id),
        "user_id": str(conversation.user_id),
        "category": conversation.category,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
    }


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Get a specific conversation by ID.
    
    Args:
        conversation_id: UUID of the conversation
        
    Returns:
        Conversation details
    """
    chat_service = get_chat_service(db)
    conversation = chat_service.get_conversation(conversation_id, current_user.id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Build response manually to avoid model_validate issues
    return {
        "id": str(conversation.id),
        "user_id": str(conversation.user_id),
        "category": conversation.category,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
    }


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: UUID,
    limit: Optional[int] = Query(None, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Get messages for a conversation.
    
    Args:
        conversation_id: UUID of the conversation
        limit: Optional limit on number of messages to return
        
    Returns:
        List of messages in chronological order
    """
    chat_service = get_chat_service(db)
    messages = chat_service.get_conversation_messages(
        conversation_id=conversation_id,
        user_id=current_user.id,
        limit=limit
    )
    
    # Build response manually to avoid model_validate issues
    return [
        {
            "id": str(msg.id),
            "conversation_id": str(msg.conversation_id),
            "role": msg.role,
            "message": msg.message,
            "response_data": msg.response_data,
            "metadata": msg.message_metadata,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "updated_at": msg.updated_at.isoformat() if msg.updated_at else None,
        }
        for msg in messages
    ]


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: UUID,
    message_data: MessageCreate,
    engagement_id: Optional[UUID] = Query(None, description="Optional engagement ID to find diagnostic context"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Send a message in a conversation and get AI response.
    
    This endpoint:
    1. Saves the user message
    2. Builds GPT context (system prompt, category prompt, diagnostic context, conversation history)
    3. Calls OpenAI to generate response
    4. Saves the assistant response
    5. Returns the assistant message
    
    Args:
        conversation_id: UUID of the conversation
        message_data: Message content
        
    Returns:
        Assistant message with AI response
    """
    import logging
    logger = logging.getLogger(__name__)
    
    chat_service = get_chat_service(db)
    
    try:
        logger.info(f"🚀 API: Sending message to conversation")

        
        assistant_message = await chat_service.send_message(
            conversation_id=conversation_id,
            user_id=current_user.id,
            message_text=message_data.message,
            limit=50,
            engagement_id=engagement_id
        )
        
        logger.info(f"✅ API: Message sent successfully")

        
        # Build response manually to avoid model_validate issues
        return {
            "id": str(assistant_message.id),
            "conversation_id": str(assistant_message.conversation_id),
            "role": assistant_message.role,
            "message": assistant_message.message,
            "response_data": assistant_message.response_data,
            "metadata": assistant_message.message_metadata,
            "created_at": assistant_message.created_at.isoformat() if assistant_message.created_at else None,
            "updated_at": assistant_message.updated_at.isoformat() if assistant_message.updated_at else None,
        }
        
    except ValueError as e:
        logger.error(f"ValueError sending message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Exception sending message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@router.post("/messages/{message_id}/create-task", status_code=status.HTTP_201_CREATED)
async def create_task_from_message(
    message_id: UUID,
    engagement_id: UUID = Query(..., description="Engagement ID to create task in"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Create a task from an assistant message.
    
    Args:
        message_id: UUID of the assistant message
        engagement_id: UUID of the engagement to create task in
        
    Returns:
        Success message with task count
    """
    chat_service = get_chat_service(db)
    
    try:
        tasks_created = chat_service.create_task_from_message(
            message_id=message_id,
            engagement_id=engagement_id,
            created_by_user_id=current_user.id
        )
        
        return {
            "success": True,
            "message": f"Created {tasks_created} task(s) from message",
            "tasks_created": tasks_created
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.post("/messages/{message_id}/create-note", status_code=status.HTTP_201_CREATED)
async def create_note_from_message(
    message_id: UUID,
    engagement_id: UUID = Query(..., description="Engagement ID to create note in"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Create a note from an assistant message.
    
    Args:
        message_id: UUID of the assistant message
        engagement_id: UUID of the engagement to create note in
        
    Returns:
        Success message with note count
    """
    chat_service = get_chat_service(db)
    
    try:
        notes_created = chat_service.create_note_from_message(
            message_id=message_id,
            engagement_id=engagement_id,
            created_by_user_id=current_user.id
        )
        
        return {
            "success": True,
            "message": f"Created {notes_created} note(s) from message",
            "notes_created": notes_created
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create note: {str(e)}"
        )

