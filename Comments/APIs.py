from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from Comments import crud, schemas, models
from database import get_db
from dependencies import get_current_active_user
from roles import RoleEnum as Role

router = APIRouter(prefix="/comments", tags=["Comments"])

@router.post("/", response_model=schemas.Comment)
def create_comment(comment: schemas.CommentCreate, db: Session = Depends(get_db),
                   current_user = Depends(get_current_active_user)):
    # Only users, employees, admin can comment
    if current_user.role not in [Role.user.value, Role.employee.value, Role.admin.value, Role.super_admin.value]:
        raise HTTPException(status_code=403, detail="Not authorized to comment")
    return crud.create_comment(db, comment)

@router.get("/grievance/{grievance_id}", response_model=List[schemas.Comment])
def get_comments(grievance_id: int, db: Session = Depends(get_db),
                 current_user = Depends(get_current_active_user)):
    return crud.get_comments_by_grievance(db, grievance_id)
