from pydantic import BaseModel

class DepartmentBase(BaseModel):
    name: str

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentOut(BaseModel):
    id: int
    name: str

class Department(DepartmentBase):
    id: int
    class Config:
        orm_mode = True
