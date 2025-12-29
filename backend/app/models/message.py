"""
Message model for chat messages in conversations
"""
from sqlalchemy import Column, String, Text, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class Message(Base):
    """
    Message represents a single message in a conversation (user or assistant).
    Stores the message text, role, and optional GPT response metadata.
    """
    __tablename__ = "messages"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    
    # Relationships
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Message content
    role = Column(String(20), nullable=False, index=True, comment="user or assistant")
    message = Column(Text, nullable=False, comment="The message content")
    
    # GPT response metadata (for assistant messages)
    response_data = Column(JSONB, nullable=True, comment="Raw GPT response data")
    message_metadata = Column(JSONB, nullable=True, comment="Additional metadata (tokens, model, etc.)")
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), index=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    def __repr__(self):
        return f"<Message(id={self.id}, conversation_id={self.conversation_id}, role='{self.role}')>"

