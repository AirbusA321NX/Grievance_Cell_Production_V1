from fastapi import APIRouter, Depends, HTTPException, status , Query
from sqlalchemy.orm import Session
from typing import List , Optional
from roles import RoleEnum as Role
from User import models as user_models
from Grievances import models as grievance_models
from . import models, schemas, crud
from database import get_db
from dependencies import get_current_active_user

router = APIRouter(prefix="/comments", tags=["Comments"])

@router.post("/", response_model=schemas.Comment)
def create_comment(comment: schemas.CommentCreate, db: Session = Depends(get_db),
                   current_user = Depends(get_current_active_user)):
    # Only users, employees, admin can comment
    if current_user.role not in [Role.user.value, Role.employee.value, Role.admin.value, Role.super_admin.value]:
        raise HTTPException(status_code=403, detail="Not authorized to comment")
    return crud.create_comment(db, comment)


@router.get("/grievance/{grievance_id}", response_model=List[schemas.Comment])
def get_comments(
        grievance_id: int,
        db: Session = Depends(get_db),
        current_user: user_models.User = Depends(get_current_active_user),
        skip: int = 0,
        limit: int = Query(100, le=200, description="Number of records per page (max 200)"),
        search: Optional[str] = None,
        sort_order: str = Query("desc", description="Sort order: 'asc' or 'desc'", regex="^(asc|desc)$")
):
    """
    Get comments for a specific grievance with pagination and search.

    Search fields:
    - content: Case-insensitive search in comment content

    Returns:
    - List of comments for the specified grievance
    - 403 if user doesn't have access to the grievance
    - 404 if grievance not found
    """
    # Check if user has access to the grievance
    grievance = db.query(grievance_models.Grievance).filter_by(id=grievance_id).first()
    if not grievance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grievance not found"
        )

    # Check permissions
    if (current_user.role == Role.user and grievance.user_id != current_user.id) or \
            (current_user.role == Role.employee and grievance.department_id != current_user.department_id) or \
            (current_user.role == Role.admin and grievance.department_id != current_user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view comments for this grievance"
        )

    # Base query
    query = db.query(models.Comment).filter(
        models.Comment.grievance_id == grievance_id
    )

    # Apply search filter if provided
    if search:
        search = f"%{search}%"
        query = query.filter(
            models.Comment.content.ilike(search)
        )

    if sort_order.lower() == "asc":
        query = query.order_by(models.Comment.created_at.asc())
    else:
        query = query.order_by(models.Comment.created_at.desc())

    # Apply pagination and return results
    return query.offset(skip).limit(limit).all()