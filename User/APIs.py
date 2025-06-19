from fastapi import APIRouter, Depends, HTTPException , status
from sqlalchemy.orm import Session
from typing import List, Union
import traceback
from User import crud
from database import get_db
from dependencies import get_current_active_user, RoleChecker
from roles import RoleEnum as Role
from Grievances import models, schemas
from . import models, schemas
from sqlalchemy.orm import joinedload

router = APIRouter(prefix="/users", tags=["Users"])

# Only admin, employee, super_admin can create users
role_admin_employee_super = RoleChecker([Role.admin, Role.employee, Role.super_admin])
role_admin = RoleChecker([Role.admin, Role.super_admin])  # Add this line

@router.post("/", response_model=schemas.UserFull, operation_id="create_new_user")
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(role_admin_employee_super),
):
    try:
        # Prevent privilege escalation: cannot create user with higher role than yourself
        role_hierarchy = [Role.user, Role.employee, Role.admin, Role.super_admin]
        creator_index = role_hierarchy.index(current_user.role)
        new_user_index = role_hierarchy.index(user.role)
        if new_user_index > creator_index:
            raise HTTPException(status_code=403, detail="Cannot create user with higher privilege than yourself.")
        return crud.create_user(db, user)
    except Exception as e:
        print("Error in create_user:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[Union[schemas.UserLimited, schemas.UserFull]], operation_id="read_all_users")
def read_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    users = crud.get_users(db)
    if current_user.role == Role.user:
        # Normal users see limited info only
        return [schemas.UserLimited.from_orm(u) for u in users]
    # Admin/Employee/Super see full info
    return [schemas.UserFull.from_orm(u) for u in users]


@router.get("/{user_id}", response_model=Union[schemas.UserLimited, schemas.UserFull], operation_id="read_user_by_id")
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    # Fetch a single user by ID
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Self or elevated roles see full info
    if current_user.id == user_id or current_user.role in [Role.admin, Role.employee, Role.super_admin]:
        return schemas.UserFull.from_orm(user)

    # Other normal users see limited info
    if current_user.role == Role.user:
        return schemas.UserLimited.from_orm(user)

    raise HTTPException(status_code=403, detail="Not authorized")


@router.get("/grievances", response_model=List[schemas.GrievanceOut])
def list_grievances(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user),
        skip: int = 0,
        limit: int = 100
):
    """
    List grievances based on user role:
    - Super Admin: All grievances
    - Admin: All grievances in their department
    - Employee: Assigned grievances in their department
    - User: Only their own grievances
    """
    query = db.query(models.Grievance)

    # Apply filters based on user role
    if current_user.role == Role.user:
        query = query.filter(models.Grievance.user_id == current_user.id)
    elif current_user.role == Role.employee:
        query = query.filter(
            (models.Grievance.department_id == current_user.department_id) &
            (models.Grievance.assigned_to == current_user.id)
        )
    elif current_user.role == Role.admin:
        query = query.filter(models.Grievance.department_id == current_user.department_id)
    # Super admin can see all grievances, no additional filter needed

    # Include related data
    query = query.options(
        joinedload(models.Grievance.user),
        joinedload(models.Grievance.department),
        joinedload(models.Grievance.assigned_to_user),
        joinedload(models.Grievance.attachments)
    ).order_by(models.Grievance.created_at.desc())

    return query.offset(skip).limit(limit).all()
@router.patch("/{user_id}/role", response_model=schemas.UserFull, operation_id="update_user_role")
def update_user_role(
        user_id: int,
        role_update: schemas.UserRoleUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(role_admin)  # Only admin can change roles
):
    """
    Update a user's role.
    Only accessible by admins.
    """
    # Check if target user exists
    db_user = crud.get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent modifying super_admin users unless current user is super_admin
    if db_user.role == Role.super_admin and current_user.role != Role.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can modify other super admins"
        )

    # Prevent promoting to super_admin unless current user is super_admin
    if role_update.role == Role.super_admin and current_user.role != Role.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can create other super admins"
        )

    # Update the role
    db_user.role = role_update.role
    db.commit()
    db.refresh(db_user)
    return db_user