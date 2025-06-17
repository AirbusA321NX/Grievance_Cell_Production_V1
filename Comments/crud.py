from sqlalchemy.orm import Session
from . import models, schemas
from datetime import datetime

def create_comment(db: Session, comment: schemas.CommentCreate):
    db_comment = models.Comment(**comment.dict(), timestamp=datetime.now())
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

def get_comments_by_grievance(db: Session, grievance_id: int):
    grievance_id = int(grievance_id)
    return db.query(models.Comment).filter(models.Comment.grievance_id == grievance_id).all()
