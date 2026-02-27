"""
Strategy Workbook model for tracking workbook generation sessions
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class StrategyWorkbook(Base):
    """
    StrategyWorkbook represents a strategy workshop workbook generation session.
    Tracks document uploads, extracted data, and generated workbook files.
    """
    __tablename__ = "strategy_workbooks"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    # Foreign keys
    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='SET NULL'), nullable=True, index=True,
                           comment="Optional link to engagement")
    diagnostic_id = Column(UUID(as_uuid=True), ForeignKey('diagnostics.id', ondelete='SET NULL'), nullable=True, index=True,
                           comment="When created from a completed diagnostic")
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    diagnostic_context = Column(JSONB, nullable=True,
                                comment="Diagnostic report/ai_analysis used as context")

    # Status tracking
    status = Column(String(50), nullable=False, server_default='draft', index=True, 
                   comment="draft, extracting, ready, failed")
    
    # File references
    uploaded_media_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True, 
                                comment="Array of Media IDs for uploaded documents")
    template_path = Column(Text, nullable=True, 
                          comment="Path to the template file used")
    generated_workbook_path = Column(Text, nullable=True, 
                                    comment="Path to the generated workbook file")
    
    # Extracted data
    extracted_data = Column(JSONB, nullable=True, 
                           comment="Structured extracted content from documents")
    
    # Metadata
    notes = Column(Text, nullable=True, comment="User notes or review comments")
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), 
                       onupdate=func.current_timestamp())
    completed_at = Column(DateTime, nullable=True, comment="When workbook generation completed")
    
    # Relationships
    engagement = relationship("Engagement", back_populates="strategy_workbooks")
    diagnostic = relationship("Diagnostic", backref="strategy_workbooks", foreign_keys=[diagnostic_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self):
        return f"<StrategyWorkbook(id={self.id}, status='{self.status}')>"
    
    def to_dict(self):
        """Convert workbook to dictionary"""
        return {
            "id": str(self.id),
            "engagement_id": str(self.engagement_id) if self.engagement_id else None,
            "diagnostic_id": str(self.diagnostic_id) if self.diagnostic_id else None,
            "created_by_user_id": str(self.created_by_user_id) if self.created_by_user_id else None,
            "diagnostic_context": self.diagnostic_context,
            "status": self.status,
            "uploaded_media_ids": [str(mid) for mid in (self.uploaded_media_ids or [])],
            "template_path": self.template_path,
            "generated_workbook_path": self.generated_workbook_path,
            "extracted_data": self.extracted_data,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

