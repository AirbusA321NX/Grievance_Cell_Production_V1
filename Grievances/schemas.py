from pydantic import BaseModel , validator
from datetime import datetime
from typing import Optional, List , Dict, ForwardRef


UserOut = ForwardRef('UserOut')

class GrievanceCreate(BaseModel):
    grievance: str
    greviance_id: Optional[int] = None
    user_id: int
    role: str
    department_id: int
    files: Optional[List[bytes]] = None

class StatusHistoryOut(BaseModel):
    status: str
    changed_at: datetime
    changed_by: UserOut

    class Config:
        orm_mode = True

class GrievanceAttachmentOut(BaseModel):
    id: int
    file_name: str
    file_path: str
    file_url: str  # Add this line
    file_type: str
    file_size: int
    created_at: datetime

    class Config:
        orm_mode = True

class AttachmentBase(BaseModel):
        file_name: str
        file_type: str
        file_size: int

class AttachmentResponse(AttachmentBase):
    id: int
    file_url: str  # URL to access the file
    uploaded_at: datetime

class GrievanceUpdate(BaseModel):
    grievance: str | None = None
    status: str | None = None
    assigned_to: int | None = None  

class GrievanceOut(BaseModel):
    id: int
    ticket_id: str
    user_id: int
    department_id: int
    assigned_to: int | None
    status: str
    created_at: datetime
    attachments: List[AttachmentResponse] = []
    status_history: List[StatusHistoryOut] = []
    timeline: List[Dict] = []  # For the timeline view

    @validator('timeline', pre=True, always=True)
    def build_timeline(cls, v, values):
        if 'status_history' in values:
            return [
                {
                    "type": "status_change",
                    "status": entry.status,
                    "timestamp": entry.changed_at.isoformat(),
                    "changed_by": entry.changed_by.email if entry.changed_by else "System"
                }
                for entry in values.get('status_history', [])
            ]
        return v

    class Config:
        orm_mode = True

class AttachmentCreate(AttachmentBase):
    file_content: bytes

    class Config:
        orm_mode = True
