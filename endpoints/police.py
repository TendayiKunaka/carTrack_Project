import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from pydantic.datetime_parse import timedelta
from sqlalchemy.orm import Session
from typing import List
import os
import crud
import models
import schemas
from auth import get_current_user, get_db, get_current_police, pwd_context
import aiofiles
from datetime import datetime, timedelta
import json

router = APIRouter(prefix="/police", tags=["police"])


# Add to crud.py:
def get_police_by_username(db: Session, username: str):
    return db.query(models.Police).filter(models.Police.username == username).first()


def create_police(db: Session, police: schemas.PoliceCreate):
    db_police = models.Police(
        badge_number=police.badge_number,
        username=police.username,
        hashed_password=pwd_context.hash(police.password),
        full_name=police.full_name,
        station=police.station
    )
    db.add(db_police)
    db.commit()
    db.refresh(db_police)
    return db_police


@router.post("/police/", response_model=schemas.Police)
def create_police(police: schemas.PoliceCreate, db: Session = Depends(get_db)):
    db_police = crud.create_police(db=db, police=police)
    if db_police is None:
        raise HTTPException(status_code=400, detail="Police officer already exists")
    return db_police


@router.post("/tickets/", response_model=schemas.Ticket)
async def create_ticket(
        ticket_data: str = Form(...),  # Change to Form and accept as string
        photo: UploadFile = File(...),
        current_user: models.Police = Depends(get_current_police),
        db: Session = Depends(get_db)
):
    """
    Create a new parking ticket with photo evidence

    Required:
    - violation_type: Type of violation
    - amount: Fine amount
    - location: Where violation occurred
    - vehicle_plate: License plate number
    - photo: Image evidence

    Returns:
    - Created ticket with all details
    """
    try:
        # Parse the JSON string from form data
        try:
            ticket_data_dict = json.loads(ticket_data)
            ticket_data_obj = schemas.TicketCreate(**ticket_data_dict)
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid ticket data format: {str(e)}"
            )

        # 1. Validate vehicle exists
        vehicle = db.query(models.Vehicle).filter(
            models.Vehicle.plate_number == ticket_data_obj.vehicle_plate
        ).first()
        if not vehicle:
            raise HTTPException(
                status_code=404,
                detail=f"Vehicle with plate {ticket_data_obj.vehicle_plate} not found"
            )

        # 2. Get vehicle owner
        user = db.query(models.User).filter(
            models.User.id == vehicle.user_id
        ).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="Vehicle owner not found"
            )

        # 3. Process photo upload
        upload_dir = "uploads/tickets"
        os.makedirs(upload_dir, exist_ok=True)

        file_ext = os.path.splitext(photo.filename)[1]
        filename = f"{uuid.uuid4()}{file_ext}"
        filepath = os.path.join(upload_dir, filename)

        async with aiofiles.open(filepath, "wb") as buffer:
            await buffer.write(await photo.read())

        photo_url = f"/{upload_dir}/{filename}"

        # 4. Create ticket
        db_ticket = models.Ticket(
            violation_type=ticket_data_obj.violation_type,
            amount=ticket_data_obj.amount,
            issue_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=30),
            photo_url=photo_url,
            location=ticket_data_obj.location,
            user_id=user.id,
            vehicle_id=vehicle.id,
            police_officer_id=current_user.id  # Changed from officer_id to police_officer_id
        )

        db.add(db_ticket)
        db.commit()
        db.refresh(db_ticket)

        return db_ticket

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating ticket: {str(e)}"
        )


@router.get("/tickets/", response_model=List[schemas.Ticket])
def get_issued_tickets(
        current_user: models.Police = Depends(get_current_police),
        db: Session = Depends(get_db)
):
    return db.query(models.Ticket).filter(models.Ticket.police_officer_id == current_user.id).all()
