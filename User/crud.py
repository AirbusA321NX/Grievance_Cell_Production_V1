from sqlalchemy.orm import Session
from . import models, schemas
from Department.models import Department
from Department.crud import create_department, get_departments
from passlib.context import CryptContext
from typing import List , Optional
import pdb
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_user(db: Session, user: schemas.UserCreate):
    # Check if department_id is provided, else use/create 'OTR'
    if user.department_id is None:
        print("No department_id provided, checking for OTR...")
        department = db.query(Department).filter_by(name="OTR").first()
        if not department:
            print("OTR not found, creating...")
            department = Department(name="OTR")
            db.add(department)
            db.commit()
            db.refresh(department)
            print("OTR created.")
        department_id = department.id
        print("Using department_id:", department_id)
    else:
        department_id = user.department_id

    db_user = models.User(
        email=user.email,
        password=get_password_hash(user.password),  # hash only if you're using secure login
        department_id=department_id,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    return user


def get_users(db: Session, role_filter: List[str] = None):
    query = db.query(models.User)
    if role_filter:
        query = query.filter(models.User.role.in_(role_filter))
    return query.all()

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

   