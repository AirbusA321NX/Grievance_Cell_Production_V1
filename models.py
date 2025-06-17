from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "user_detail"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String, index=True)

class Admin(Base):
    __tablename__ = "admin_detail"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String, index=True)

class Grievances(Base):
    __tablename__ = "Grievances"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    Grievances_content = Column(String, index=True)
    department = Column(String, index=True)
