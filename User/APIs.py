from fastapi import APIRouter, Depends, HTTPException, status , Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Union , Optional
import traceback
from datetime  import datetime
from database import get_db
from dependencies import get_current_active_user, RoleChecker
from roles import RoleEnum as Role
from Grievances import models as grievance_models
from Grievances import schemas as grievance_schemas
from . import models, schemas, crud
from Grievances.models import GrievanceStatus
from sqlalchemy.orm import joinedload
from schemas import PaginatedResponse
from .schemas import UserFull
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

router = APIRouter(prefix="/users", tags=["Users"])

# Role checkers
role_admin_employee_super = RoleChecker([Role.admin, Role.employee, Role.super_admin])
role_admin = RoleChecker([Role.admin, Role.super_admin])

@router.post("/", response_model=schemas.UserFull, operation_id="create_new_user")
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


@router.get("/", response_model=PaginatedResponse[UserFull])
def list_users(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user),
        skip: int = 0,
        limit: int = Query(100, le=200, description="Number of records per page (max 200)"),
        search: Optional[str] = None,
        role: Optional[Role] = None,
        department_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        search_fields: Optional[List[str]] = None,
        sort_by: str = "name",
        sort_order: str = "asc",
):
    """
    List all users with pagination, search, filtering, and sorting.

    - Super admins can see all users
    - Admins can see users in their department and all regular users

    Search fields (when search parameter is provided):
    - name: Search in user's name
    - email: Search in user's email
    - phone: Search in user's phone number
    - department: Search in department name
    - role: Search in role

    Sort fields (sort_by parameter):
    - name (default)
    - email
    - created_at
    - updated_at
    - last_login
    - department (sorts by department name)
    - role

    Sort order: 'asc' (default) or 'desc'
    """
    # Import models locally to avoid circular imports
    from Department import models as dept_models

    # Check admin access
    if current_user.role not in [Role.admin, Role.super_admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view all users"
        )

    # Base query with eager loading
    query = db.query(models.User).options(
        joinedload(models.User.department)
    )

    # Role-based filtering
    if current_user.role == Role.admin:
        query = query.filter(
            (models.User.department_id == current_user.department_id) |
            (models.User.role == Role.user)  # Admins can see all users in their dept + all regular users
        )
    # Super admin can see all users

    # Apply filters
    if role:
        query = query.filter(models.User.role == role)
    if department_id:
        query = query.filter(models.User.department_id == department_id)
    if is_active is not None:
        query = query.filter(models.User.is_active == is_active)

    # Apply search
    if search:
        search = f"%{search}%"
        search_conditions = []

        # If specific fields are provided, search only in those
        if search_fields:
            if "name" in search_fields:
                search_conditions.append(models.User.name.ilike(search))
            if "email" in search_fields:
                search_conditions.append(models.User.email.ilike(search))
            if "phone" in search_fields:
                search_conditions.append(models.User.phone.ilike(search))
            if "department" in search_fields:
                query = query.join(dept_models.Department)
                search_conditions.append(dept_models.Department.name.ilike(search))
            if "role" in search_fields:
                search_conditions.append(models.User.role.ilike(search))
        else:
            # Default search across all relevant fields
            query = query.join(
                dept_models.Department,
                models.User.department_id == dept_models.Department.id,
                isouter=True
            )
            search_conditions = [
                models.User.name.ilike(search),
                models.User.email.ilike(search),
                models.User.phone.ilike(search),
                dept_models.Department.name.ilike(search),
                models.User.role.ilike(search)
            ]

        query = query.filter(or_(*search_conditions))

    # Apply sorting
    sort_field = None
    if sort_by == "name":
        sort_field = models.User.name
    elif sort_by == "email":
        sort_field = models.User.email
    elif sort_by == "created_at":
        sort_field = models.User.created_at
    elif sort_by == "updated_at":
        sort_field = models.User.updated_at
    elif sort_by == "last_login":
        sort_field = models.User.last_login
    elif sort_by == "department":
        query = query.join(dept_models.Department)
        sort_field = dept_models.Department.name
    elif sort_by == "role":
        sort_field = models.User.role

    # Apply sort order
    if sort_field is not None:
        if sort_order.lower() == "asc":
            query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(sort_field.desc())
    else:
        # Default sorting
        query = query.order_by(models.User.name.asc())

    # Apply pagination
    total = query.count()
    users = query.offset(skip).limit(limit).all()

    return {
        "items": [schemas.UserFull.from_orm(u) for u in users],
        "total": total,
        "limit": limit,
        "offset": skip
    }

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

@router.get("/grievances/", response_model=List[grievance_schemas.GrievanceOut])
def list_user_grievances(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_active_user),
        skip: int = 0,
        limit: int = Query(100, le=200, description="Number of records per page (max 200)"),
        # Filter parameters
        status: Optional[GrievanceStatus] = None,
        user_id: Optional[int] = None,
        department_id: Optional[int] = None,
        assigned_to: Optional[int] = None,
        search: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        # Sorting parameters
        sort_by: str = Query("created_at",
                             description="Field to sort by (created_at, status, user_id, department_id)"),
        sort_order: str = Query("desc",
                                description="Sort order (asc or desc)",
                                regex="^(asc|desc)$")
):
    """
    List grievances with advanced filtering, sorting, and pagination.

    Permissions:
    - Regular users: Can only see their own grievances
    - Employees: Can see grievances in their department assigned to them
    - Admins: Can see all grievances in their department with filtering options
    - Super Admins: Can see all grievances across departments with full filtering
    """
    # Base query with eager loading
    query = db.query(grievance_models.Grievance).options(
        joinedload(grievance_models.Grievance.user),
        joinedload(grievance_models.Grievance.department),
        joinedload(grievance_models.Grievance.employee),
        joinedload(grievance_models.Grievance.attachments),
        joinedload(grievance_models.Grievance.status_history)
    )

    # Role-based filtering
    if current_user.role == Role.user:
        query = query.filter(grievance_models.Grievance.user_id == current_user.id)
    elif current_user.role == Role.employee:
        query = query.filter(
            (grievance_models.Grievance.department_id == current_user.department_id) &
            (grievance_models.Grievance.assigned_to == current_user.id)
        )
    elif current_user.role in [Role.admin, Role.super_admin]:
        # Admins can only see their department's grievances unless super admin
        if current_user.role == Role.admin:
            query = query.filter(
                grievance_models.Grievance.department_id == current_user.department_id
            )

        # Additional filters for admin/super_admin
        if status:
            query = query.filter(grievance_models.Grievance.status == status)
        if user_id:
            query = query.filter(grievance_models.Grievance.user_id == user_id)
        if department_id:
            if current_user.role == Role.super_admin:  # Only super admin can filter by any department
                query = query.filter(
                    grievance_models.Grievance.department_id == department_id
                )
        if assigned_to:
            query = query.filter(
                grievance_models.Grievance.assigned_to == assigned_to
            )

    # Apply global filters (for all roles)
    if created_after:
        query = query.filter(grievance_models.Grievance.created_at >= created_after)
    if created_before:
        query = query.filter(grievance_models.Grievance.created_at <= created_before)
    if search:
        search = f"%{search}%"
        query = query.filter(
            or_(
                grievance_models.Grievance.grievance_content.ilike(search),
                grievance_models.Grievance.ticket_id.ilike(search)
            )
        )

    # Apply sorting
    sort_field = getattr(
        grievance_models.Grievance,
        sort_by if hasattr(grievance_models.Grievance, sort_by) else "created_at",
        grievance_models.Grievance.created_at
    )

    # Apply sort order
    if sort_order.lower() == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())

    # Apply pagination
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