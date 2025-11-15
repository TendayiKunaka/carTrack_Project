from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from starlette import status

import crud
import models
import schemas
from auth import get_current_user, get_db, get_current_registry_worker, pwd_context

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/", response_model=schemas.User)
def read_user_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/", response_model=schemas.User)
def create_user(
        user: schemas.UserCreate,
        db: Session = Depends(get_db)
):
    # Check if username already exists
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Check if email already exists
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    hashed_password = pwd_context.hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        email_notifications=user.email_notifications,
        hashed_password=hashed_password,
        address=user.address,
        town=user.town,
        city=user.city,
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Create initial balance for the user
    balance = models.UserBalance(
        user_id=db_user.id,
        available_balance=0.0,
        loan_balance=0.0,
        total_balance=0.0,
        borrowed_amount=0.0,
        used_borrowed_amount=0.0
    )
    db.add(balance)
    db.commit()

    # Return user with balance field as None (since it's optional now)
    # The balance field in User schema expects a float, not a UserBalance object
    user_response = {
        "id": db_user.id,
        "username": db_user.username,
        "email": db_user.email,
        "full_name": db_user.full_name,
        "phone_number": db_user.phone_number,
        "address": db_user.address,
        "town": db_user.town,
        "city": db_user.city,
        "email_notifications": db_user.email_notifications,
        "is_active": db_user.is_active,
        "balance": None  # Set to None since it's optional
    }

    return schemas.User(**user_response)


@router.get("/vehicles/available", response_model=List[schemas.Vehicle])
async def get_available_vehicles(
        plate_search: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """
    Get vehicles that are not assigned to any user (available for registration)
    """
    query = db.query(models.Vehicle).filter(models.Vehicle.user_id == None)

    if plate_search:
        query = query.filter(models.Vehicle.plate_number.ilike(f"%{plate_search}%"))

    return query.all()


@router.post("/vehicles/add-by-plate", response_model=schemas.Vehicle)
async def add_vehicle_by_plate(
        plate_request: schemas.VehiclePlateRequest,  # We'll create this schema
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Add an existing vehicle to user's account by plate number
    """
    # Check if vehicle exists
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == plate_request.plate_number
    ).first()

    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle with this plate number not found"
        )

    # Check if vehicle already belongs to another user
    if vehicle.user_id and vehicle.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vehicle already belongs to another user"
        )

    # Check if vehicle already belongs to this user
    if vehicle.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vehicle already belongs to you"
        )

    # Assign vehicle to user
    vehicle.user_id = current_user.id

    # Create ownership history record
    ownership = models.OwnershipHistory(
        vehicle_id=vehicle.id,
        user_id=current_user.id,
        start_date=datetime.utcnow()
    )
    db.add(ownership)

    db.commit()
    db.refresh(vehicle)

    return vehicle


@router.get("/vehicles/", response_model=List[schemas.Vehicle])
def get_vehicles(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.get_user_vehicles(db, user_id=current_user.id)


@router.get("/tickets/", response_model=List[schemas.Ticket])
def get_tickets(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    return crud.get_user_tickets(db, user_id=current_user.id)


@router.delete("/vehicles/{plate_number}", response_model=dict)
async def remove_vehicle_from_account(
        plate_number: str,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Remove a vehicle from user's account
    """
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == plate_number,
        models.Vehicle.user_id == current_user.id
    ).first()

    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found in your account"
        )

    # End current ownership
    current_ownership = db.query(models.OwnershipHistory).filter(
        models.OwnershipHistory.vehicle_id == vehicle.id,
        models.OwnershipHistory.end_date == None
    ).first()

    if current_ownership:
        current_ownership.end_date = datetime.utcnow()

    # Remove vehicle from user
    vehicle.user_id = None

    db.commit()

    return {"message": f"Vehicle {plate_number} removed from your account"}
