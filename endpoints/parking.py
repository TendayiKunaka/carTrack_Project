from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from starlette.responses import StreamingResponse
import crud
import models
import schemas
from auth import get_current_user, get_db, pwd_context, get_current_parking_worker
import uuid
import os
from enum import Enum
from fastapi.responses import FileResponse
from fastapi.encoders import jsonable_encoder
import pandas as pd
import io

router = APIRouter(prefix="/parking", tags=["parking"])

# Configure your upload directory (create this in your project root)
UPLOAD_DIR = "uploads/tickets"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def create_parking_worker(db: Session, worker: schemas.ParkingWorkerCreate):
    db_worker = models.ParkingWorker(
        employee_id=worker.employee_id,
        username=worker.username,
        hashed_password=pwd_context.hash(worker.password),
        full_name=worker.full_name,
        zone=worker.zone
    )
    db.add(db_worker)
    db.commit()
    db.refresh(db_worker)
    return db_worker


@router.post("/workers/", response_model=schemas.ParkingWorker)
def create_parking_worker(
        worker: schemas.ParkingWorkerCreate,
        db: Session = Depends(get_db)
):
    db_worker = crud.get_parking_worker_by_username(db, username=worker.username)
    if db_worker:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_parking_worker(db=db, worker=worker)


@router.get("/sessions/", response_model=List[schemas.ParkingSession])
def get_parking_sessions(
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db)
):
    return db.query(models.ParkingSession).filter(
        models.ParkingSession.zone == current_worker.zone
    ).all()


@router.post("/tickets/", response_model=schemas.Ticket)
async def create_ticket(
        plate_number: str = Form(..., description="Vehicle plate number"),
        violation_type: str = Form(..., description="Type of violation"),
        amount: float = Form(..., gt=0, description="Fine amount"),
        location: str = Form(..., description="Violation location"),
        notes: Optional[str] = Form(None, description="Additional notes"),
        photo: Optional[UploadFile] = File(None),
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db)
):
    """
    Issue a new parking ticket using form data and automatically deduct from customer balance parking_expired,
    no_parking_zone, handicap_zone, fire_hydrant, other
    """
    # Validate violation type
    valid_violations = ["parking_expired", "no_parking_zone", "handicap_zone", "fire_hydrant", "other"]
    if violation_type not in valid_violations:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid violation type. Must be one of: {', '.join(valid_violations)}"
        )

    # Check if vehicle exists
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == plate_number
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Check if user exists
    user = db.query(models.User).filter(models.User.id == vehicle.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Vehicle owner not found")

    # Handle photo upload
    photo_url = None
    if photo:
        try:
            # Generate unique filename
            file_ext = os.path.splitext(photo.filename)[1]
            filename = f"{uuid.uuid4()}{file_ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)

            # Save the file
            with open(filepath, "wb") as buffer:
                content = await photo.read()
                buffer.write(content)
            photo_url = f"/{UPLOAD_DIR}/{filename}"
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error processing photo: {str(e)}"
            )

    # Process payment automatically
    payment_success, used_loan, payment_message = crud.process_ticket_payment(
        db, user.id, amount, f"{violation_type} ticket at {location}"
    )

    if not payment_success:
        raise HTTPException(
            status_code=400,
            detail=f"Could not process ticket payment: {payment_message}"
        )

    # Create ticket
    try:
        db_ticket = models.Ticket(
            violation_type=violation_type,
            amount=amount,
            issue_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=14),
            photo_url=photo_url,
            location=location,
            notes=notes,
            user_id=user.id,
            vehicle_id=vehicle.id,
            parking_worker_id=current_worker.id,
            is_paid=True,  # Auto-mark as paid since we deducted automatically
            is_disputed=False,
            dispute_resolved=False
        )

        db.add(db_ticket)
        db.commit()
        db.refresh(db_ticket)

        # Add payment info to response
        db_ticket.payment_message = payment_message
        db_ticket.used_loan = used_loan

        return db_ticket
    except Exception as e:
        db.rollback()
        # If ticket creation fails, refund the payment
        try:
            if used_loan:
                # Reverse the loan transaction
                crud.update_user_balance(db, user.id, amount, "repayment")
            else:
                # Refund the deducted balance
                crud.update_user_balance(db, user.id, amount, "deposit")
        except:
            pass  # If refund fails, at least we tried

        raise HTTPException(
            status_code=500,
            detail=f"Error creating ticket: {str(e)}"
        )


@router.get("/tickets/{ticket_id}", response_model=schemas.Ticket)
def get_ticket(
        ticket_id: int,
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db)
):
    """
    Get specific ticket details
    """
    ticket = db.query(models.Ticket).filter(
        models.Ticket.id == ticket_id,
        models.Ticket.location == current_worker.zone
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return ticket


@router.patch("/tickets/{ticket_id}/pay", response_model=schemas.Ticket)
def mark_ticket_as_paid(
        ticket_id: int,
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db)
):
    """
    Manually mark a ticket as paid (with balance deduction)
    """
    ticket = db.query(models.Ticket).filter(
        models.Ticket.id == ticket_id,
        models.Ticket.location == current_worker.zone
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.is_paid:
        raise HTTPException(status_code=400, detail="Ticket already paid")

    # Process payment
    success, message = crud.manual_ticket_payment(db, ticket_id)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    db.refresh(ticket)
    ticket.payment_message = message
    return ticket


@router.patch("/tickets/{ticket_id}/dispute", response_model=schemas.Ticket)
def dispute_ticket(
        ticket_id: int,
        dispute_data: schemas.TicketDispute,
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db)
):
    """
    Mark a ticket as disputed
    """
    ticket = db.query(models.Ticket).filter(
        models.Ticket.id == ticket_id,
        models.Ticket.location == current_worker.zone
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.is_disputed = True
    ticket.dispute_reason = dispute_data.reason
    db.commit()
    db.refresh(ticket)
    return ticket


# Add after your existing ticket endpoints

@router.put("/tickets/{ticket_id}", response_model=schemas.Ticket)
def update_ticket(
        ticket_id: int,
        ticket_update: schemas.TicketUpdate,
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db)
):
    """
    Update ticket details (for admin/worker use)
    """
    ticket = db.query(models.Ticket).filter(
        models.Ticket.id == ticket_id,
        models.Ticket.location == current_worker.zone
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    update_data = ticket_update.dict(exclude_unset=True)
    for field in update_data:
        setattr(ticket, field, update_data[field])

    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/tickets/bulk", response_model=List[schemas.Ticket])
async def create_bulk_tickets(
        bulk_data: schemas.BulkTicketCreate,
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db)
):
    """
    Create multiple tickets at once (for batch processing)
    """
    created_tickets = []
    for ticket_data in bulk_data.tickets:
        vehicle = db.query(models.Vehicle).filter(
            models.Vehicle.plate_number == ticket_data.plate_number
        ).first()

        if not vehicle:
            continue  # or you might want to collect errors

        db_ticket = models.Ticket(
            **ticket_data.dict(),
            issue_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=14),
            user_id=vehicle.user_id,
            vehicle_id=vehicle.id,
            officer_id=current_worker.id,
            location=current_worker.zone
        )
        db.add(db_ticket)
        created_tickets.append(db_ticket)

    db.commit()
    return created_tickets


@router.post("/tickets/{ticket_id}/manual-payment")
def process_manual_payment(
        ticket_id: int,
        payment_method: str = Form(..., description="Payment method: cash, card, etc."),
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db)
):
    """
    Process manual payment for a ticket (when auto-deduction fails)
    """
    ticket = db.query(models.Ticket).filter(
        models.Ticket.id == ticket_id,
        models.Ticket.location == current_worker.zone
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.is_paid:
        raise HTTPException(status_code=400, detail="Ticket already paid")

    # Mark as paid without balance deduction (manual payment)
    ticket.is_paid = True
    ticket.payment_method = payment_method
    db.commit()
    db.refresh(ticket)

    return {
        "message": f"Ticket marked as paid via {payment_method}",
        "ticket": ticket
    }


@router.get("/tickets/stats", response_model=schemas.TicketStats)
def get_ticket_stats(
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db),
        start_date: datetime = None,
        end_date: datetime = None
):
    """
    Get statistics about tickets in the worker's zone
    """
    query = db.query(models.Ticket).filter(
        models.Ticket.location == current_worker.zone
    )

    if start_date:
        query = query.filter(models.Ticket.issue_date >= start_date)
    if end_date:
        query = query.filter(models.Ticket.issue_date <= end_date)

    tickets = query.all()

    stats = {
        "total_tickets": len(tickets),
        "paid_tickets": sum(1 for t in tickets if t.is_paid),
        "unpaid_tickets": sum(1 for t in tickets if not t.is_paid),
        "disputed_tickets": sum(1 for t in tickets if t.is_disputed),
        "total_revenue": sum(t.amount for t in tickets if t.is_paid),
        "by_violation_type": {}
    }

    # Count by violation type
    violation_types = set(t.violation_type for t in tickets)
    for vt in violation_types:
        stats["by_violation_type"][vt] = sum(1 for t in tickets if t.violation_type == vt)

    return stats


@router.get("/tickets/export/csv")
def export_tickets_csv(
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db),
        paid_status: Optional[bool] = None
):
    """
    Export tickets to CSV
    """
    query = db.query(models.Ticket).filter(
        models.Ticket.location == current_worker.zone
    )

    if paid_status is not None:
        query = query.filter(models.Ticket.is_paid == paid_status)

    tickets = query.all()

    # Convert to DataFrame
    data = [{
        "id": t.id,
        "plate_number": t.vehicle.plate_number,
        "violation_type": t.violation_type,
        "amount": t.amount,
        "issue_date": t.issue_date,
        "due_date": t.due_date,
        "is_paid": t.is_paid,
        "location": t.location
    } for t in tickets]

    df = pd.DataFrame(data)
    stream = io.StringIO()
    df.to_csv(stream, index=False)

    response = StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=tickets_{current_worker.zone}_{datetime.now().date()}.csv"
        }
    )

    return response


@router.get("/tickets/{ticket_id}/photo")
async def get_ticket_photo(
        ticket_id: int,
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db)
):
    """
    Get the photo associated with a ticket
    """
    ticket = db.query(models.Ticket).filter(
        models.Ticket.id == ticket_id,
        models.Ticket.location == current_worker.zone
    ).first()

    if not ticket or not ticket.photo_url:
        raise HTTPException(status_code=404, detail="Photo not found")

    photo_path = ticket.photo_url.lstrip('/')
    if not os.path.exists(photo_path):
        raise HTTPException(status_code=404, detail="Photo file not found")

    return FileResponse(photo_path)


@router.post("/tickets/{ticket_id}/resolve-dispute", response_model=schemas.Ticket)
def resolve_dispute(
        ticket_id: int,
        resolution: schemas.TicketUpdate,
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db)
):
    """
    Resolve a disputed ticket
    """
    ticket = db.query(models.Ticket).filter(
        models.Ticket.id == ticket_id,
        models.Ticket.location == current_worker.zone,
        models.Ticket.is_disputed == True
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Disputed ticket not found")

    if resolution.is_disputed is not None:
        ticket.is_disputed = resolution.is_disputed
    if resolution.dispute_resolved is not None:
        ticket.dispute_resolved = resolution.dispute_resolved
    if resolution.amount is not None:
        ticket.amount = resolution.amount

    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/tickets/user/{user_id}", response_model=List[schemas.Ticket])
def get_user_tickets(
        user_id: int,
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db),
        include_paid: bool = False
):
    """
    Get all tickets for a specific user in the worker's zone
    """
    query = db.query(models.Ticket).filter(
        models.Ticket.user_id == user_id,
        models.Ticket.location == current_worker.zone
    )

    if not include_paid:
        query = query.filter(models.Ticket.is_paid == False)

    return query.all()


@router.get("/tickets/vehicle/{plate_number}", response_model=List[schemas.Ticket])
def get_vehicle_tickets(
        plate_number: str,
        current_worker: models.ParkingWorker = Depends(get_current_parking_worker),
        db: Session = Depends(get_db)
):
    """
    Get all tickets for a specific vehicle in the worker's zone
    """
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == plate_number
    ).first()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return db.query(models.Ticket).filter(
        models.Ticket.vehicle_id == vehicle.id,
        models.Ticket.location == current_worker.zone
    ).all()
