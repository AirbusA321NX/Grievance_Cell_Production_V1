from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SQLEnum
from pydantic import BaseModel
from enum import Enum as PyEnum
from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property
from database import Base
import os

from database import Base


class GrievanceStatus(str, PyEnum):
    pending = "pending"
    solved = "solved"
    not_solved = "not_solved"
    closed = "closed"

class Grievance(Base):
    __tablename__ = "grievances"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    department_id = Column(Integer, ForeignKey("departments.id"))
    grievance_content = Column(String)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    status        = Column(SQLEnum(GrievanceStatus), default=GrievanceStatus.pending)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    resolved_by   = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at   = Column(DateTime(timezone=True), nullable=True)
    user = relationship("User", foreign_keys=[user_id])
    department = relationship("Department")
    status_history = relationship("GrievanceStatusHistory", back_populates="grievance", cascade="all, delete-orphan")
    employee = relationship("User", foreign_keys=[assigned_to])
    resolver = relationship("User", foreign_keys=[resolved_by])
    attachments = relationship("GrievanceAttachment", back_populates="grievance", cascade="all, delete-orphan")



class GrievanceStatusHistory(Base):
    __tablename__ = "grievance_status_history"

    id = Column(Integer, primary_key=True, index=True)
    grievance_id = Column(Integer, ForeignKey('grievances.id', ondelete="CASCADE"))
    status = Column(String)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    changed_by_id = Column(Integer, ForeignKey('users.id'))
    notes = Column(String, nullable=True)

    grievance = relationship("Grievance", back_populates="status_history")
    changed_by = relationship("User")

    def __repr__(self):
        return f"<GrievanceStatusHistory {self.id} - {self.status}>"


class GrievanceAttachment(Base):
    __tablename__ = "grievance_attachments"

    id = Column(Integer, primary_key=True, index=True)
    grievance_id = Column(Integer, ForeignKey("grievances.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to grievance
    grievance = relationship("Grievance", back_populates="attachments")

    @hybrid_property
    def file_url(self):
        return f"/grievances/attachments/{self.id}"

    @file_url.expression
    def file_url(cls):
        return func.concat("/grievances/attachments/", cls.id)

    class GrievanceAttachmentResponse(BaseModel):
        id: int
        file_name: str
        file_path: str
        file_url: str
        file_type: str
        file_size: int
        created_at: datetime

        class Config:
            from_attributes = True
