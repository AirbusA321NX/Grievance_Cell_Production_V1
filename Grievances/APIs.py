import os
from fastapi import APIRouter, Depends, HTTPException, status , Form , UploadFile , File
from sqlalchemy.orm import Session
from typing import List , Optional
from fastapi.security import HTTPBearer
from Grievances import crud, schemas , models
from User.models import User
from database import get_db
from dependencies import get_current_active_user, RoleChecker
from roles import RoleEnum
from Department import models as dept_models
from fastapi.responses import FileResponse
from pathlib import Path
from file_utils import save_upload_file, get_mime_type, delete_file

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
        current_user: User = Depends(get_current_active_user),
):
    """
    Create a new grievance with optional file attachments.
    Only users can create grievances.
    """
    # Only users can raise grievances
    if current_user.role != RoleEnum.user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only users can create grievances"
        )

    # Initialize variables at the start
    db_grievance = None
    file_path = None
    attachment = None

    try:
        # Create the grievance using the GrievanceCreate schema
        grievance_data = schemas.GrievanceCreate(
            grievance=grievance,
            department_id=department_id,
            user_id=current_user.id,
            role=current_user.role.value
        )

        # Create the grievance using crud
        db_grievance = crud.create_grievance(db, grievance_data, current_user.id)

        # Process file uploads if any
        if files:
            for file in files:
                if file and file.filename:  # Check if file exists and has a name
                    try:
                        # Save the file
                        file_path, original_filename, file_size = await save_upload_file(file)

                        # Create attachment record
                        attachment = models.GrievanceAttachment(
                            grievance_id=db_grievance.id,
                            file_path=file_path,
                            file_name=original_filename,
                            file_type=file.content_type or get_mime_type(original_filename),
                            file_size=file_size
                        )
                        db.add(attachment)

                    except Exception as file_error:
                        # If file upload fails, clean up and re-raise
                        if file_path and os.path.exists(file_path):
                            delete_file(file_path)
                        raise file_error

            db.commit()
            db.refresh(db_grievance)

        return db_grievance

    except Exception as e:
        db.rollback()
        # Clean up any uploaded files if there was an error
        if db_grievance and files:
            for file in files:
                if (file and hasattr(file, 'filename') and file.filename and
                        file_path and os.path.exists(file_path)):
                    try:
                        delete_file(file_path)
                    except Exception:
                        pass  # Don't let cleanup errors mask the original error

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating grievance: {str(e)}"
        )
@router.get("/", response_model=List[schemas.GrievanceOut])
def read_grievances(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role == RoleEnum.user:
        return crud.get_grievances_by_user(db, current_user.id)
    if current_user.role == RoleEnum.employee:
        return crud.get_grievances_by_employee(db, current_user.id)
    if current_user.role in (RoleEnum.admin, RoleEnum.super_admin):
        return crud.get_all_grievances(db)
    raise HTTPException(status_code=403, detail="Not authorized")

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