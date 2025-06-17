from pydantic import BaseModel
from datetime import datetime

class CommentBase(BaseModel):
    grievance_id: int
    user_id: int
    content: str

class CommentCreate(CommentBase):
    pass

class Comment(CommentBase):
    id: int
    timestamp: datetime
    class Config:
        orm_mode = True
