from pydantic import BaseModel , Field
from pydantic.networks import EmailStr
from typing import Optional, List, ForwardRef , Dict , Any , Literal
from roles import RoleEnum
from enum  import Enum
from datetime import datetime

# Forward references
GrievanceAttachmentOut = ForwardRef('GrievanceAttachmentOut')

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
    id: int
    email: str
    name: str
    role: str
    department_id: Optional[int] = None
    is_active: bool = True

    class Config:
        from_attributes = True  # This was called orm_mode in Pydantic v1
        # For Pydantic v2 compatibility, also add:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


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
        from_attributes = True

class UserSortBy(str, Enum):
    name = "name"
    email = "email"
    created_at = "created_at"
    updated_at = "updated_at"
    last_login = "last_login"
    department = "department"
    role = "role"

class UserSortRequest(BaseModel):
    sort_by: UserSortBy = Field(default=UserSortBy.name)
    sort_order: Literal["asc", "desc"] = Field(
        default="desc",
        description="Sort order: 'asc' for ascending, 'desc' for descending"
    )

class GrievanceOut(BaseModel):
    id: int
    ticket_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    status: str
    user: 'UserOut'
    department: 'DepartmentOut'
    assigned_to: Optional[UserOut] = None
    resolved_by: Optional[UserOut] = None
    resolved_at: Optional[datetime] = None
    attachments: List[Dict[str, Any]] = []
    grievance_content: str  # Added this field

    class Config:
        from_attributes = True

if __name__ != "__main__":

    pass