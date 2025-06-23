import os
from fastapi import APIRouter, Depends, HTTPException, status , Form , UploadFile , File
from sqlalchemy.orm import Session , joinedload
from typing import List , Optional
from fastapi.security import HTTPBearer
from Grievances import crud
from database import get_db
from roles import RoleEnum
from Department import models as dept_models
from fastapi.responses import FileResponse
from dependencies import get_current_active_user, RoleChecker
from pathlib import Path
from file_utils import save_upload_file, get_mime_type, delete_file
from . import models, schemas
from User.models import User
import os
import uuid
from .models import GrievanceStatus, GrievanceStatusHistory

# Role-based dependencies
admin_only = RoleChecker([RoleEnum.admin, RoleEnum.super_admin])
user_only  = RoleChecker([RoleEnum.user])
emp_only   = RoleChecker([RoleEnum.employee])

router = APIRouter(prefix="/grievances", tags=["Grievances"])

bearer_scheme = HTTPBearer()


@router.post("/", response_model=schemas.GrievanceOut)
async def create_grievance(
        grievance: str = Form(...),
        department_id: int = Form(...),
        files: Optional[List[UploadFile]] = File(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(user_only),  # Only users can create grievances
):
    """
    Create a new grievance with optional file attachments.
    """
    db_grievance = None
    try:
        # Create the grievance
        db_grievance = models.Grievance(
            ticket_id=str(uuid.uuid4()),
            user_id=current_user.id,
            department_id=department_id,
            grievance_content=grievance,
            status=GrievanceStatus.pending
        )
        db.add(db_grievance)
        db.commit()
        db.refresh(db_grievance)

        # Handle file uploads if any
        if files:
            for file in files:
                # Save the file and get its details
                file_path = await save_upload_file(file)
                file_size = os.path.getsize(file_path)
                file_type = get_mime_type(file_path)

                # Create attachment record
                attachment = models.GrievanceAttachment(
                    grievance_id=db_grievance.id,
                    file_path=str(file_path),
                    file_name=file.filename,
                    file_type=file_type,
                    file_size=file_size
                )
                db.add(attachment)

            db.commit()
            db.refresh(db_grievance)

        # Create initial status history
        status_history = models.GrievanceStatusHistory(
            grievance_id=db_grievance.id,
            status=GrievanceStatus.pending,
            changed_by_id=current_user.id
        )
        db.add(status_history)
        db.commit()
        db.refresh(db_grievance)

        return db_grievance

    except Exception as e:
        # Clean up in case of error
        if db_grievance and db_grievance.id:
            if files:
                for file in files:
                    if os.path.exists(file_path):
                        os.remove(file_path)
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating grievance: {str(e)}"
        )

@router.get("/", response_model=List[schemas.GrievanceOut])
def read_grievances(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip:  int =0,
    limit : int = 100
):
    query = db.query(models.Grievance)
    if current_user.role == RoleEnum.user:
        query = query.filter(models.Grievance.user_id == current_user.id)
    elif current_user.role == RoleEnum.employee:
        query = query.filter(
            (models.Grievance.department_id == current_user.department_id) &
            (models.Grievance.assigned_to == current_user.id)
        )
    elif current_user.role == RoleEnum.admin:
        query = query.filter(models.Grievance.department_id == current_user.department_id)
        # Super admin can see all grievances (no filter)

        # Include related data
    query = query.options(
        joinedload(models.Grievance.user),
        joinedload(models.Grievance.department),
        joinedload(models.Grievance.assigned_to_user),
        joinedload(models.Grievance.attachments)
    ).order_by(models.Grievance.created_at.desc())

    return query.offset(skip).limit(limit).all()

@router.post("/assign", status_code=status.HTTP_204_NO_CONTENT)
def assign_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    # Only admin and super_admin can assign pending grievances
    crud.assign_grievances_to_employees(db)
    return

@router.post("/{grievance_id}/resolve", response_model=schemas.GrievanceOut)
def resolve_grievance(
    grievance_id: int,
    resolver_id: int,
    solved: bool = True,
    db: Session = Depends(get_db),
):
    """
    Mark a grievance solved or not_solved.
    - resolved_by and resolved_at will be set here.
    """
    updated = crud.resolve_grievance(db, grievance_id, resolver_id, solved)
    if not updated:
        raise HTTPException(404, "Grievance not found")
    return updated



@router.get("/{ticket_id}", response_model=schemas.GrievanceOut)
def get_grievance_by_id(
        ticket_id: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
):
    """
    Get a specific grievance by ticket ID.
    Only admins can access any ticket. Regular users can only access their own tickets.
    """
    grievance = crud.get_grievance_by_ticket_id(db, ticket_id)
    if not grievance:
        raise HTTPException(status_code=404, detail="Grievance not found")

    # Admin can access any ticket
    if current_user.role in (RoleEnum.admin, RoleEnum.super_admin):
        return grievance

    # Regular users can only access their own tickets
    if current_user.role == RoleEnum.user and grievance.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this grievance"
        )

    # Employees can access tickets assigned to them
    if current_user.role == RoleEnum.employee and grievance.assigned_to != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this grievance"
        )

    return grievance

@router.post("/{ticket_id}/transfer", response_model=schemas.GrievanceOut)
async def transfer_grievance_department(
    ticket_id: str,
    new_department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),  # Only admins can transfer tickets
):
    """
    Transfer a grievance to a different department.
    
    Only administrators can transfer tickets between departments.
    This will reset the assignment and status of the ticket.
    """
    # Check if the department exists
    department = db.query(dept_models.Department).filter(dept_models.Department.id == new_department_id).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {new_department_id} not found"
        )

    # Transfer the grievance
    updated_grievance = crud.transfer_grievance_department(
        db=db,
        ticket_id=ticket_id,
        new_department_id=new_department_id,
        transferred_by=current_user.id
    )
    
    if not updated_grievance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grievance with ticket ID {ticket_id} not found"
        )
    
    return updated_grievance


@router.get("/attachments/{attachment_id}", response_class=FileResponse)
async def download_attachment(
        attachment_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
):
    """
    Download an attachment file.

    Users can only download attachments from their own grievances or if they're an admin.
    """
    # Get the attachment
    attachment = db.query(models.GrievanceAttachment).filter(
        models.GrievanceAttachment.id == attachment_id
    ).first()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found"
        )

    # Check permissions
    if current_user.role not in (RoleEnum.admin, RoleEnum.super_admin):
        grievance = db.query(models.Grievance).filter(
            models.Grievance.id == attachment.grievance_id,
            models.Grievance.user_id == current_user.id
        ).first()

        if not grievance:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this attachment"
            )

    # Check if file exists
    file_path = Path(attachment.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on server"
        )

    return FileResponse(
        path=file_path,
        filename=attachment.file_name,
        media_type=attachment.file_type
    )


@router.get("/test", response_model=List[schemas.GrievanceOut])
def test_endpoint(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    """
    Test endpoint to check if the API is working.
    """
    # Simple query without complex joins
    grievances = db.query(models.Grievance).filter(
        models.Grievance.user_id == current_user.id
    ).limit(10).all()

    # Convert to list of dicts
    result = []
    for g in grievances:
        result.append({
            **g.__dict__,
            "attachments": [a.__dict__ for a in g.attachments],
            "status_history": [
                {
                    "status": h.status,
                    "changed_at": h.changed_at,
                    "changed_by": {
                        "id": h.changed_by.id,
                        "email": h.changed_by.email
                    } if h.changed_by else None
                }
                for h in g.status_history
            ]
        })

    return result

@router.get("/", response_model=List[schemas.GrievanceOut])
def list_grievances(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    department_id: Optional[int] = None,
    assigned_to: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all grievances with filtering options.
    - Admins see all grievances
    - Employees see assigned grievances
    - Users see only their own grievances
    """
    query = db.query(models.Grievance).options(
        joinedload(models.Grievance.user),
        joinedload(models.Grievance.department),
        joinedload(models.Grievance.employee),
        joinedload(models.Grievance.status_history).joinedload(models.GrievanceStatusHistory.changed_by),
        joinedload(models.Grievance.attachments)
    )

    # Apply role-based filtering
    if current_user.role == RoleEnum.user:
        query = query.filter(models.Grievance.user_id == current_user.id)
    elif current_user.role == RoleEnum.employee:
        query = query.filter(
            (models.Grievance.assigned_to == current_user.id) |
            (models.Grievance.user_id == current_user.id)
        )
    # Admin can see all, no additional filter needed

    # Apply filters
    if status:
        query = query.filter(models.Grievance.status == status)
    if department_id:
        query = query.filter(models.Grievance.department_id == department_id)
    if assigned_to is not None:
        query = query.filter(models.Grievance.assigned_to == assigned_to)

    # Apply pagination
    grievances = query.offset(skip).limit(limit).all()
    return grievances