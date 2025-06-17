from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SQLEnum
from enum import Enum as PyEnum
from sqlalchemy.sql import func
from datetime import datetime
from database import Base
from roles import RoleEnum

class GrievanceStatus(str, PyEnum):
    pending = "pending"
    solved = "solved"
    not_solved = "not_solved"

class Grievance(Base):
    __tablename__ = "grievances"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    department_id = Column(Integer, ForeignKey("departments.id"))
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    status        = Column(SQLEnum(GrievanceStatus), default=GrievanceStatus.pending)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    # NEW fields:
    resolved_by   = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at   = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    department = relationship("Department")
    employee = relationship("User", foreign_keys=[assigned_to])
    resolver = relationship("User", foreign_keys=[resolved_by])