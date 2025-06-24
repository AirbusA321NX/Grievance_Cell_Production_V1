# schemas/base.py
from typing import List, TypeVar, Generic
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

T = TypeVar('T')

class PaginatedResponse(GenericModel, Generic[T]):
    items: List[T]
    total: int = Field(..., description="Total number of items matching the query")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Current offset")