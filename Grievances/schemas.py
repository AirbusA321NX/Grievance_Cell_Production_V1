from pydantic import BaseModel, validator , Field
from datetime import datetime
from typing import List, Optional, Dict, Any

class StatusHistoryOut(BaseModel):
    id: int
    status: str
    changed_at: datetime
    changed_by: Dict[str, Any]

    class Config:
        from_attributes = True

class AttachmentBase(BaseModel):
    file_name: str
    file_type: str
    file_size: int

class AttachmentCreate(AttachmentBase):
    file_content: bytes

class AttachmentResponse(AttachmentBase):
    id: int
    file_url: str
    uploaded_at: datetime

    class Config:
        orm_mode = True

class GrievanceBase(BaseModel):
    grievance_content: str
    user_id: int
    department_id: int

class GrievanceCreate(GrievanceBase):
    pass

class GrievanceTransferRequest(BaseModel):
    new_department_id: int
    notes: Optional[str] = None

class GrievanceStatusUpdate(BaseModel):
    status: str  # e.g., "open", "in_progress", "resolved", "closed"
    notes: Optional[str] = None

class GrievanceUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[int] = None


class GrievanceSearchResult(BaseModel):
    data: List['GrievanceOut']
    total_count: int
    filters: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class GrievanceOut(GrievanceBase):
    id: int
    ticket_id: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    attachments: List[Dict[str, Any]] = []
    status_history: List[Dict[str, Any]] = []
    timeline: List[Dict[str, Any]] = []

    @validator('timeline', pre=True, always=True)
    def build_timeline(cls, v, values):
        if 'status_history' in values and values['status_history']:
            return [
                {
                    "type": "status_change",
                    "status": entry.get('status'),
                    "timestamp": entry.get('changed_at').isoformat() if entry.get('changed_at') else None,
                    "changed_by": entry.get('changed_by', {}).get('email', 'System')
                }
                for entry in values['status_history']
            ]
        return []

    class Config:
        from_attributes = True

    # Add this class to Grievances/schemas.py
    class GrievanceAttachmentOut(BaseModel):
            id: int
            file_name: str
            file_path: str
            file_url: str
            file_type: str
            file_size: int
            uploaded_at: datetime


            class Config:
                from_attributes = True