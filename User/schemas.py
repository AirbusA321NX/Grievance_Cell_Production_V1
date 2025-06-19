# User/schemas.py
from pydantic import BaseModel
from pydantic.networks import EmailStr
from typing import Optional
from roles import RoleEnum
from pydantic import ConfigDict

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