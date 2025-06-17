from sqlalchemy import Column, Integer, String, Enum, ForeignKey
from database import Base
from roles import RoleEnum

class User(Base):
    __tablename__ = "users"


    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    role = Column(Enum(RoleEnum), default=RoleEnum.user)
