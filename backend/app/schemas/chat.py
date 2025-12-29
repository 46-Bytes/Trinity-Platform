"""
Pydantic schemas for Chat models
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ==================== CONVERSATION SCHEMAS ====================

class ConversationBase(BaseModel):
    """Base conversation schema"""
    category: str = Field(..., description="Conversation category (general, diagnostic, finance, etc.)")
    title: Optional[str] = Field(None, description="Optional conversation title")


class ConversationCreate(ConversationBase):
    """Schema for creating a new conversation"""
    diagnostic_id: Optional[UUID] = Field(None, description="Optional diagnostic ID to link conversation to")


class ConversationResponse(ConversationBase):
    """Schema for conversation response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """Schema for list of conversations"""
    conversations: List[ConversationResponse]


# ==================== MESSAGE SCHEMAS ====================

class MessageBase(BaseModel):
    """Base message schema"""
    message: str = Field(..., description="Message content")


class MessageCreate(MessageBase):
    """Schema for creating a new message"""
    pass


class MessageResponse(MessageBase):
    """Schema for message response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    conversation_id: UUID
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    response_data: Optional[dict] = Field(None, description="Raw GPT response data")
    message_metadata: Optional[dict] = Field(None, description="Additional metadata", alias="metadata")
    created_at: datetime
    updated_at: datetime

