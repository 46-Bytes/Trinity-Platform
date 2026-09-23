"""
Buyer access: the engagement binding, the released folders, and the access log.

A buyer is an external party invited to look at one engagement's data room and
nothing else. The isolation is deliberately not expressed through
check_engagement_access - that function default-denies an unknown role, and it
stays that way, so no existing advisor, client or admin route can serve a buyer
by accident. Access is instead resolved forward from EngagementBuyer: the
engagement comes from the binding, never from a path parameter the buyer
supplies.

Allowed values for the String status columns live in services/buyer_rules.py and
are validated there, matching the rest of app/models (no CheckConstraints).
"""
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Index, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class EngagementBuyer(Base):
    """
    One buyer's access to one engagement.

    Revoking sets `status` and leaves the row in place: the brief calls
    revocation a soft delete, and the access log has to stay attributable to a
    real binding afterwards. Re-granting flips the same row back, so a buyer
    keeps their id and their history.

    A buyer account belongs to exactly one engagement at a time. That is
    enforced by a partial unique index on user_id covering only live bindings,
    so a revoked binding does not block the same person being invited elsewhere.
    """
    __tablename__ = "engagement_buyer"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    engagement_id = Column(
        UUID(as_uuid=True),
        ForeignKey('engagements.id', ondelete='CASCADE', name='fk_engagement_buyer_engagement'),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE', name='fk_engagement_buyer_user'),
        nullable=False,
    )

    status = Column(String(50), nullable=False, server_default='active',
                    comment="'active' or 'revoked'; revoking never deletes the row")
    invited_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL', name='fk_engagement_buyer_invited_by'),
        nullable=True,
    )
    # Recorded only. The NDA is handled outside Trinity and does not gate access.
    nda_signed_date = Column(Date, nullable=True,
                             comment="When the NDA was signed outside Trinity; record only")

    is_deleted = Column(Boolean, nullable=False, server_default='false')
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('engagement_id', 'user_id', name='uq_engagement_buyer_engagement_user'),
        # One live engagement per buyer account. Revoked and deleted rows drop
        # out, so a buyer can be invited elsewhere once their access has ended.
        Index(
            'uq_engagement_buyer_one_live_per_user', 'user_id', unique=True,
            postgresql_where=text("status = 'active' AND is_deleted = false"),
        ),
        Index('ix_engagement_buyer_engagement', 'engagement_id', 'status'),
    )

    def __repr__(self):
        return f"<EngagementBuyer engagement={self.engagement_id} user={self.user_id} status={self.status}>"


class EngagementReleasedFolder(Base):
    """
    A data room folder the advisor has released to buyers.

    Keyed by the due diligence category and sub-item, which is the folder the
    brief and the mockup describe ("one folder per DD category and sub-item")
    and the unit the mockup's own buyer panel releases. Nothing is released by
    default; a folder with no row here is invisible to every buyer.

    ASSUMPTION carried from the mockup: release is per sub-item, not per file
    and not per category. Confirm with the client before Drive lands.
    """
    __tablename__ = "engagement_released_folder"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    engagement_id = Column(
        UUID(as_uuid=True),
        ForeignKey('engagements.id', ondelete='CASCADE', name='fk_engagement_released_folder_engagement'),
        nullable=False,
    )
    category_code = Column(String(10), nullable=False, comment="DD category number, e.g. '3'")
    sub_item_code = Column(String(10), nullable=False, comment="DD sub-item number, e.g. '3.1'")

    released_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL', name='fk_engagement_released_folder_released_by'),
        nullable=True,
    )
    released_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    is_deleted = Column(Boolean, nullable=False, server_default='false')
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('engagement_id', 'category_code', 'sub_item_code',
                         name='uq_engagement_released_folder_folder'),
    )

    def __repr__(self):
        return f"<EngagementReleasedFolder {self.engagement_id} {self.category_code}/{self.sub_item_code}>"


class BuyerAccessLog(Base):
    """
    Every open and download a buyer performs, as the brief requires.

    Append-only: rows are never updated or deleted, including when the binding
    is revoked, so the record of who saw what survives the access ending. The
    engagement is stored alongside the user because a buyer may be re-invited
    elsewhere later and the log must stay attributable to the right sale.
    """
    __tablename__ = "buyer_access_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    engagement_id = Column(
        UUID(as_uuid=True),
        ForeignKey('engagements.id', ondelete='CASCADE', name='fk_buyer_access_log_engagement'),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE', name='fk_buyer_access_log_user'),
        nullable=False,
    )
    media_id = Column(
        UUID(as_uuid=True),
        ForeignKey('media.id', ondelete='SET NULL', name='fk_buyer_access_log_media'),
        nullable=True, comment="The document, when the action was about one",
    )

    action = Column(String(30), nullable=False, comment="'list', 'view' or 'download'")
    detail = Column(Text, nullable=True, comment="What was listed or opened, for actions with no media row")

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        Index('ix_buyer_access_log_engagement_time', 'engagement_id', 'created_at'),
        Index('ix_buyer_access_log_user_time', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f"<BuyerAccessLog {self.action} user={self.user_id} engagement={self.engagement_id}>"
