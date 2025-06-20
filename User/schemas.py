# User/schemas.py
from pydantic import BaseModel, ConfigDict
from pydantic.networks import EmailStr
from typing import Optional, List, ForwardRef
from roles import RoleEnum
from datetime import datetime
from Grievances.schemas import GrievanceAttachmentOut
from Grievances.models import GrievanceStatus, Grievance

# Forward references

class PasswordReset(BaseModel):
    email: EmailStr
    new_password: str


class UserBase(BaseModel):
    user_id: Optional[int] = None
    email: str
    password: str
    department_id: Optional[int] = None
    role: RoleEnum = RoleEnum.user


class UserLimited(UserBase):
    # no department info here
    pass


class UserFull(BaseModel):
    id: int
    email: EmailStr
    department_id: int
    role: RoleEnum

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
        use_enum_values = True
        from_attributes = True


class UserCreate(BaseModel):
    user_id: Optional[int] = None
    email: str
    password: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    role: RoleEnum


class UserRoleUpdate(BaseModel):
    role: RoleEnum


class DepartmentOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: RoleEnum
    department_id: Optional[int] = None
    department: Optional[DepartmentOut] = None

    class Config:
        orm_mode = True


class GrievanceOut(BaseModel):
    id: int
    ticket_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    status: str
    user: UserOut
    department: DepartmentOut
    assigned_to: Optional[UserOut] = None
    resolved_by: Optional[UserOut] = None
    resolved_at: Optional[datetime] = None
    attachments: List[GrievanceAttachmentOut] = []
    grievance_content: str  # Added this field

    class Config:
        orm_mode = True


# Update forward references
UserOut.update_forward_refs()
GrievanceOut.update_forward_refs()