from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class GrievanceCreate(BaseModel):
    grievance: str
    greviance_id: Optional[int] = None
    user_id: int
    role: str
    department_id: int
    files: Optional[List[bytes]] = None

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

    class Config:
        orm_mode = True

class AttachmentCreate(AttachmentBase):
    file_content: bytes

    class Config:
        orm_mode = True