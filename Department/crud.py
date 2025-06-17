from sqlalchemy.orm import Session
from . import models, schemas

def create_department(db: Session, department: schemas.DepartmentCreate):
    db_department = models.Department(name=department.name)
    db.add(db_department)
    db.commit()
    db.refresh(db_department)
    return db_department

def get_departments(db: Session):
    return db.query(models.Department).all()