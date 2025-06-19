from sqlalchemy.orm import Session
from . import models, schemas
from User.models import User
from .models import GrievanceStatus
from roles import RoleEnum
import uuid
import datetime

def create_grievance(db: Session, grievance: schemas.GrievanceCreate, user_id: int):
    # Generate unique ticket ID
    ticket = str(uuid.uuid4())
    db_g = models.Grievance(
        ticket_id=ticket,
        user_id=user_id,
        department_id=grievance.department_id,
        grievance_content=grievance.grievance
    )
    db.add(db_g)
    db.commit()
    db.refresh(db_g)
    return db_g

def assign_grievances_to_employees(db: Session):
    # All unassigned grievances
    pend = db.query(models.Grievance)\
             .filter(models.Grievance.assigned_to.is_(None))\
             .all()
    # All employees
    emps = db.query(User).filter(User.role == RoleEnum.employee).all()
    if not emps:
        return
    # Round-robin assign
    for i, g in enumerate(pend):
        g.assigned_to = emps[i % len(emps)].id
    db.commit()

def get_grievance_by_ticket_id(db: Session, ticket_id: str):
    """
    Retrieve a grievance by its ticket ID.
    Returns None if no grievance is found with the given ticket ID.
    """
    return db.query(models.Grievance).filter(models.Grievance.ticket_id == ticket_id).first()


def get_grievances_by_user(db: Session, user_id: int):
    return db.query(models.Grievance)\
             .filter(models.Grievance.user_id == user_id)\
             .all()

def get_grievances_by_employee(db: Session, employee_id: int):
    return db.query(models.Grievance)\
             .filter(models.Grievance.assigned_to == employee_id)\
             .all()

def get_all_grievances(db: Session):
    return db.query(models.Grievance).all()

def resolve_grievance(
    db: Session,
    grievance_id: int,
    resolver_id: int,
    solved: bool = True
) -> models.Grievance | None:

    # 1) Fetch the grievance
    g = db.query(models.Grievance).filter(models.Grievance.id == grievance_id).first()
    if not g:
        return None


    g.status = GrievanceStatus.solved if solved else GrievanceStatus.not_solved

    # 3) Record resolver and timestamp
    g.resolved_by = resolver_id
    g.resolved_at = datetime.datetime.utcnow()


    db.commit()
    db.refresh(g)
    return g


def transfer_grievance_department(
        db: Session,
        ticket_id: str,
        new_department_id: int,
        transferred_by: int
) -> models.Grievance | None:
    """
    Transfer a grievance to a different department.

    Args:
        db: Database session
        ticket_id: The ID of the ticket to transfer
        new_department_id: The ID of the department to transfer to
        transferred_by: The ID of the user initiating the transfer (must be admin)

    Returns:
        The updated grievance if successful, None otherwise
    """
    # Find the grievance
    grievance = get_grievance_by_ticket_id(db, ticket_id)
    if not grievance:
        return None

    # Update the department and reset assignment
    grievance.department_id = new_department_id
    grievance.assigned_to = None  # Reset assignment when transferring departments
    grievance.status = models.GrievanceStatus.pending  # Reset status

    # Add transfer history or log if needed
    # For example, you might want to log this transfer in a separate table

    db.commit()
    db.refresh(grievance)
    return grievance