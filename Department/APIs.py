from fastapi import APIRouter, Depends, HTTPException , Query , status
from sqlalchemy.orm import Session
from typing import List , Optional
from . import crud, schemas , models
from database import get_db
from dependencies import get_current_active_user, RoleChecker
from roles import RoleEnum as Role
from User.models import User
from .schemas import PaginatedResponse, Department as DepartmentSchema

router = APIRouter(prefix="/departments", tags=["Departments"])

role_admin = RoleChecker([Role.admin, Role.super_admin])

@router.post("/", response_model=schemas.Department)
def create_department(dept: schemas.DepartmentCreate, db: Session = Depends(get_db),
      current_user: User = Depends(role_admin)):
    return crud.create_department(db, dept)

@router.get("/", response_model=List[schemas.Department])
def read_departments(db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_active_user)):
        # Only admin, super_admin, and employees can see departments (users cannot)
        if current_user.role not in [Role.admin.value, Role.employee.value, Role.super_admin.value]:
            raise HTTPException(status_code=403, detail="Not authorized to view departments")
        return crud.get_departments(db)


@router.get("/", response_model=PaginatedResponse[DepartmentSchema])
def list_departments(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        skip: int = 0,
        limit: int = Query(100, le=200, description="Number of records per page (max 200)"),
        search: Optional[str] = None
):
    """
    List all departments with pagination.
    Only admin, super_admin, and employees can see departments (users cannot)
    """
    if current_user.role not in [Role.admin, Role.super_admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view departments"
        )

    query = db.query(models.Department)

    # Apply search filter if provided
    if search:
        search = f"%{search}%"
        query = query.filter(
            models.Department.name.ilike(search)
        )

    items = query.offset(skip).limit(limit).all()
    # get total count
    total = query.count()
    # Apply pagination
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": skip
    }