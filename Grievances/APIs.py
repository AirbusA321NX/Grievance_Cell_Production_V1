from fastapi import APIRouter, Depends, HTTPException, status , Form , UploadFile , File , Query
from sqlalchemy.orm import Session , joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_
from typing import List , Optional , Dict , Any
from fastapi.security import HTTPBearer
from Grievances import crud
from database import get_db
from roles import RoleEnum
from fastapi.responses import FileResponse
from dependencies import get_current_active_user, RoleChecker
from file_utils import save_upload_file, get_mime_type
from . import models, schemas
from datetime import datetime
import os
import uuid
from .models import GrievanceStatus
from User import models as user_models
from Department import models as dept_models
from User.models import User
from schemas.base import PaginatedResponse
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

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
    file_path = None
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
                file_path, original_filename, file_size = save_upload_file(file)
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
                    if 'file_path' in locals() and file_path and os.path.exists(file_path):
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
        transfer_data: schemas.GrievanceTransferRequest,  # Using the new schema
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
):
    """
    Transfer a grievance to a different department.

    - Admins can transfer within their department
    - Super admins can transfer across any department
    - Maintains audit trail of transfers
    """
    # Get the grievance with relationships
    grievance = db.query(models.Grievance).filter(
        models.Grievance.ticket_id == ticket_id
    ).options(
        joinedload(models.Grievance.department)
    ).first()

    if not grievance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grievance with ticket ID {ticket_id} not found"
        )

    # Check permissions
    if current_user.role not in [RoleEnum.admin, RoleEnum.super_admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can transfer grievances"
        )

    # For non-super admins, check department
    if current_user.role == RoleEnum.admin:
        if grievance.department_id != current_user.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only transfer grievances from your department"
            )

    # Check if new department exists
    new_department = db.query(dept_models.Department).filter(
        dept_models.Department.id == transfer_data.new_department_id
    ).first()

    if not new_department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {transfer_data.new_department_id} not found"
        )

    # Prevent transferring to same department
    if grievance.department_id == transfer_data.new_department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grievance is already in this department"
        )

    try:
        # Create status history entry
        status_history = models.GrievanceStatusHistory(
            grievance_id=grievance.id,
            status=f"transferred_to_{new_department.name.lower().replace(' ', '_')}",
            changed_by_id=current_user.id,
            notes=transfer_data.notes or f"Transferred to {new_department.name} department"
        )

        # Update grievance
        old_department_id = grievance.department_id
        grievance.department_id = transfer_data.new_department_id
        grievance.assigned_to = None  # Unassign when transferring
        grievance.updated_at = datetime.utcnow()

        db.add(status_history)
        db.commit()
        db.refresh(grievance)


        return grievance

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error transferring grievance: {str(e)}"
        )

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
    current_user: User = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 10
):
    query = db.query(models.Grievance).filter(
        models.Grievance.user_id == current_user.id
    )

    # Get total count before pagination
    total = query.count()
    """
    Test endpoint to check if the API is working.
    Returns paginated grievances for the current user with related data.
    """
    # Query with eager loading of relationships
    grievances = db.query(models.Grievance).options(
        joinedload(models.Grievance.attachments),
        joinedload(models.Grievance.status_history).joinedload(models.GrievanceStatusHistory.changed_by)
    ).filter(
        models.Grievance.user_id == current_user.id
    ).offset(skip).limit(limit).all()

    # Convert to list of dictionaries with proper serialization
    items = []
    for g in grievances:
        grievance_data = {
            "id": g.id,
            "ticket_id": g.ticket_id,
            "grievance_content": g.grievance_content,
            "status": g.status,
            "created_at": g.created_at,
            "updated_at": g.updated_at,
            "user_id": g.user_id,
            "department_id": g.department_id,
            "assigned_to": g.assigned_to,
            "attachments": [
                {
                    "id": a.id,
                    "file_name": a.file_name,
                    "file_path": a.file_path,
                    "file_url": a.file_url,
                    "file_type": a.file_type,
                    "file_size": a.file_size,
                    "uploaded_at": a.uploaded_at
                } for a in g.attachments
            ],
            "status_history": [
                {
                    "id": h.id,
                    "status": h.status,
                    "changed_at": h.changed_at,
                    "changed_by": {
                        "id": h.changed_by.id,
                        "email": h.changed_by.email,
                        "name": h.changed_by.name
                    } if h.changed_by else None,
                    "notes": h.notes
                } for h in g.status_history
            ]
        }
        items.append(grievance_data)

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": skip
    }

@router.get("/", response_model=List[schemas.GrievanceOut])
def list_grievances(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    department_id: Optional[int] = None,
    assigned_to: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc"
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
    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return {
    "items": items,
    "total": total,
    "limit": limit,
    "offset": skip
}
class GrievanceResponse(schemas.GrievanceOut):
    user: Optional[Dict[str , Any]] = None
    department: Optional[Dict[str , Any]] = None
    attachments: List[Dict[str, Any]] = []
    status_history: List[schemas.StatusHistoryOut] = []

    class Config:
        from_attributes = True

@router.get("/search/", response_model=PaginatedResponse[schemas.GrievanceOut])
def search_grievances(
db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    # Search parameters
    q: Optional[str] = Query(None, description="Search term (searches in content, ticket_id, user name, department name)"),
    status: Optional[str] = None,
    department_id: Optional[int] = None,
    user_id: Optional[int] = None,
    assigned_to: Optional[int] = None,
    resolved_by: Optional[int] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    resolved_after: Optional[datetime] = None,
    resolved_before: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc"

):
    """
    Advanced grievance search with full-text and filtering capabilities.
    Returns both results and total count.
    """
    # Base query
    query = db.query(models.Grievance)

    query = query.options(
        joinedload(models.Grievance.user),
        joinedload(models.Grievance.department),
        joinedload(models.Grievance.attachments),
        joinedload(models.Grievance.status_history).joinedload(models.GrievanceStatusHistory.changed_by)
    )



    # Apply role-based filtering
    if current_user.role == RoleEnum.user:
        query = query.filter(models.Grievance.user_id == current_user.id)
    elif current_user.role == RoleEnum.employee:
        query = query.filter(
            (models.Grievance.department_id == current_user.department_id) &
            (models.Grievance.assigned_to == current_user.id)
        )
    elif current_user.role == RoleEnum.admin:
        query = query.filter(
            models.Grievance.department_id == current_user.department_id
        )

    # Apply search filters
    if q:
        search = f"%{q}%"
        query = query.join(
            user_models.User,
            models.Grievance.user_id == user_models.User.id
        ).join(
            dept_models.Department,
            models.Grievance.department_id == dept_models.Department.id
        ).filter(
            or_(
                models.Grievance.grievance_content.ilike(search),
                models.Grievance.ticket_id.ilike(search),
                user_models.User.name.ilike(search),
                dept_models.Department.name.ilike(search)
            )
        )

    # Apply other filters
    if status:
        query = query.filter(models.Grievance.status == status)
    if department_id:
        query = query.filter(models.Grievance.department_id == department_id)
    if user_id:
        query = query.filter(models.Grievance.user_id == user_id)
    if assigned_to:
        query = query.filter(models.Grievance.assigned_to == assigned_to)
    if resolved_by:
        query = query.filter(models.Grievance.resolved_by == resolved_by)
    if created_after:
        query = query.filter(models.Grievance.created_at >= created_after)
    if created_before:
        query = query.filter(models.Grievance.created_at <= created_before)
    if resolved_after:
        query = query.filter(models.Grievance.resolved_at >= resolved_after)
    if resolved_before:
        query = query.filter(models.Grievance.resolved_at <= resolved_before)

    # Get total count before pagination
    total_count = query.count()

    # Apply sorting
    sort_field = getattr(models.Grievance, sort_by, None)
    if sort_field is None:
        sort_field = models.Grievance.created_at

    if sort_order.lower() == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())

    # Apply pagination
    items = query.offset(skip).limit(limit).all()

    return {
        "data": items,
        "total_count": total_count,
        "filters": {
            "search_term": q,
            "status": status,
            "department_id": department_id,
            "user_id": user_id,
            "assigned_to": assigned_to,
            "resolved_by": resolved_by,
            "created_after": created_after.isoformat() if created_after else None,
            "created_before": created_before.isoformat() if created_before else None,
            "resolved_after": resolved_after.isoformat() if resolved_after else None,
            "resolved_before": resolved_before.isoformat() if resolved_before else None,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
    }