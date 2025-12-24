"""
Conversation model for chat sessions with Trinity AI
"""
from sqlalchemy import Column, String, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class Conversation(Base):
    """
    Conversation represents a chat session with Trinity AI.
    Can be categorized (general, diagnostic, finance, etc.)
    """
    __tablename__ = "conversations"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    
    # Relationships
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Conversation metadata
    category = Column(String(50), nullable=False, server_default='general', index=True,
                     comment="general, diagnostic, finance, legal, operations, etc.")
    title = Column(String(255), nullable=True, comment="Optional conversation title")
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    diagnostics = relationship("Diagnostic", back_populates="conversation")
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id}, category='{self.category}')>"

