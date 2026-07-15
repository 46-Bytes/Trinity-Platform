"""
AI Field Privacy model — stores per-field AI inclusion flags for questionnaires.
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class AIFieldPrivacy(Base):
    """
    Tracks which questionnaire fields are included in or excluded from AI processing.
    One row per (questionnaire_type, field_name) pair. Absence = included (default on).
    """
    __tablename__ = "ai_field_privacy"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    questionnaire_type = Column(String(50), nullable=False, index=True,
                                comment="sale_ready | value_builder")
    field_name = Column(String(255), nullable=False,
                        comment="Matches the 'name' key in the questionnaire JSON")
    include_in_ai = Column(Boolean, nullable=False, default=True,
                           comment="True = send to Claude; False = strip from AI payload")

    updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'),
                                nullable=True, index=True)
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())

    updated_by = relationship("User", foreign_keys=[updated_by_user_id])

    __table_args__ = (
        UniqueConstraint("questionnaire_type", "field_name", name="uq_ai_field_privacy_type_field"),
    )

    def __repr__(self):
        return (
            f"<AIFieldPrivacy(type={self.questionnaire_type!r}, "
            f"field={self.field_name!r}, include={self.include_in_ai})>"
        )
