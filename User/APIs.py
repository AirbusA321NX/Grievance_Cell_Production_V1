from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Union
import traceback
from database import get_db
from dependencies import get_current_active_user, RoleChecker
from roles import RoleEnum as Role
from Grievances import models as grievance_models
from Grievances import schemas as grievance_schemas
from . import models, schemas, crud
from sqlalchemy.orm import joinedload

router = APIRouter(prefix="/users", tags=["Users"])

# Role checkers
role_admin_employee_super = RoleChecker([Role.admin, Role.employee, Role.super_admin])
role_admin = RoleChecker([Role.admin, Role.super_admin])

@router.post("/", response_model=schemas.UserFull, operation_id="create_user")
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(role_admin_employee_super),
):
    try:
        # Prevent privilege escalation
        role_hierarchy = [Role.user, Role.employee, Role.admin, Role.super_admin]
        creator_index = role_hierarchy.index(current_user.role)
        new_user_index = role_hierarchy.index(user.role)
        if new_user_index > creator_index:
            raise HTTPException(
                status_code=403,
                detail="Cannot create user with higher privilege than yourself."
            )
        return crud.create_user(db, user)
    except Exception as e:
        print("Error in create_user:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[Union[schemas.UserLimited, schemas.UserFull]],
           operation_id="list_users")
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    users = crud.get_users(db)
    if current_user.role == Role.user:
        return [schemas.UserLimited.from_orm(u) for u in users]
    return [schemas.UserFull.from_orm(u) for u in users]

@router.get("/{user_id}", response_model=Union[schemas.UserLimited, schemas.UserFull],
           operation_id="get_user")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.id == user_id or current_user.role in [Role.admin, Role.employee, Role.super_admin]:
        return schemas.UserFull.from_orm(user)

    if current_user.role == Role.user:
        return schemas.UserLimited.from_orm(user)

    raise HTTPException(status_code=403, detail="Not authorized")

@router.get("/grievances/", response_model=List[grievance_schemas.GrievanceOut],
           operation_id="list_user_grievances")
def list_user_grievances(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 100
):
    query = db.query(grievance_models.Grievance)

    if current_user.role == Role.user:
        query = query.filter(grievance_models.Grievance.user_id == current_user.id)
    elif current_user.role == Role.employee:
        query = query.filter(
            (grievance_models.Grievance.department_id == current_user.department_id) &
            (grievance_models.Grievance.assigned_to == current_user.id)
        )
    elif current_user.role == Role.admin:
        query = query.filter(grievance_models.Grievance.department_id == current_user.department_id)

    query = query.options(
        joinedload(grievance_models.Grievance.user),
        joinedload(grievance_models.Grievance.department),
        joinedload(grievance_models.Grievance.employee),
        joinedload(grievance_models.Grievance.attachments)
    ).order_by(grievance_models.Grievance.created_at.desc())

    return query.offset(skip).limit(limit).all()

@router.patch("/{user_id}/role", response_model=schemas.UserFull,
             operation_id="update_user_role")
def update_user_role(
    user_id: int,
    role_update: schemas.UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(role_admin)
):
    db_user = crud.get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.role == Role.super_admin and current_user.role != Role.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can modify other super admins"
        )

    if role_update.role == Role.super_admin and current_user.role != Role.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can create other super admins"
        )

    db_user.role = role_update.role
    db.commit()
    db.refresh(db_user)
    return db_user