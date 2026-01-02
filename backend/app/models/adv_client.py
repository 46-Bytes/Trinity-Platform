"""
Advisor-Client association model for many-to-many relationships.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from ..database import Base


class AdvisorClient(Base):
    """
    Association table for many-to-many relationship between advisors and clients.
    This bridge table allows:
    - One advisor to have multiple clients
    - One client to have multiple advisors
    - Tracking when the association was created
    """
    __tablename__ = "advisor_client"
    id = Column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4,unique=True,nullable=False,comment="Unique identifier for the association")
    advisor_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'),nullable=False,index=True, comment="Foreign key to users table (advisor)") 
    client_id = Column(UUID(as_uuid=True),ForeignKey('users.id', ondelete='CASCADE'),nullable=False,index=True,comment="Foreign key to users table (client)")
    status = Column(String(50),nullable=False,server_default='active',index=True,comment="Association status: active, inactive, suspended")
    created_at = Column( DateTime,nullable=False,server_default=func.current_timestamp(),comment="When the association was created" )
    updated_at = Column(DateTime,nullable=False,server_default=func.current_timestamp(),onupdate=func.current_timestamp(),comment="When the association was last updated")  
    __table_args__ = (UniqueConstraint('advisor_id', 'client_id', name='uq_advisor_client'),) 
    advisor = relationship("User", foreign_keys=[advisor_id], backref="client_associations_as_advisor")
    client = relationship("User", foreign_keys=[client_id], backref="advisor_associations_as_client")
    
    def __repr__(self):
        return f"<AdvisorClient(advisor_id={self.advisor_id}, client_id={self.client_id}, status='{self.status}')>"

