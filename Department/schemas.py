from typing import List, TypeVar, Generic
from pydantic import BaseModel, Field

T = TypeVar('T')

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

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int = Field(..., description="Total number of items matching the query")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Current offset")
