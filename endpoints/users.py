from fastapi import APIRouter, Depends, HTTPException, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from starlette import status

import crud
import models
import schemas
from auth import get_current_user, get_db, get_current_registry_worker, pwd_context

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/vehicles/search/{plate}", response_model=schemas.VehicleSearchResult)
def search_vehicle(
        plate: str, db: Session = Depends(get_db)):
    vehicle = crud.get_vehicle_by_plate(db, plate_number=plate)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Get related data
    accidents = db.query(models.Accident).filter(models.Accident.vehicle_id == vehicle.id).all()
    ownership_history = db.query(models.OwnershipHistory).filter(
        models.OwnershipHistory.vehicle_id == vehicle.id
    ).all()
    tickets = db.query(models.Ticket).filter(models.Ticket.vehicle_id == vehicle.id).all()
    parking_sessions = db.query(models.ParkingSession).filter(
        models.ParkingSession.vehicle_id == vehicle.id
    ).all()
    conditions = crud.get_vehicle_conditions(db, vehicle_id=vehicle.id)

    return schemas.VehicleSearchResult(
        vehicle=vehicle,
        accidents=accidents,
        ownership_history=ownership_history,
        tickets=tickets,
        parking_sessions=parking_sessions,
        conditions=conditions
    )


# In routers/users.py
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


# In endpoints/users.py
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
        "email_notifications": db_user.email_notifications,
        "is_active": db_user.is_active,
        "balance": None  # Set to None since it's optional
    }

    return schemas.User(**user_response)


@router.get("/me/", response_model=schemas.User)
def read_user_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/vehicles/", response_model=schemas.Vehicle)
def add_vehicle(
        vehicle: schemas.VehicleCreate,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Check if plate already exists
    existing_vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == vehicle.plate_number
    ).first()
    if existing_vehicle:
        raise HTTPException(status_code=400, detail="Vehicle with this plate already exists")

    db_vehicle = models.Vehicle(
        plate_number=vehicle.plate_number,
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        color=vehicle.color,
        mileage_at_import=vehicle.mileage_at_import,
        road_worthiness_expiry=vehicle.road_worthiness_expiry,
        user_id=current_user.id
        # Registry fields remain null until updated by registry
    )
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


# In routers/users.py
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


@router.post("/tickets/{ticket_id}/dispute")
def dispute_ticket(
        ticket_id: int,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    ticket = db.query(models.Ticket).filter(
        models.Ticket.id == ticket_id,
        models.Ticket.user_id == current_user.id
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.is_disputed = True
    db.commit()
    db.refresh(ticket)
    return {"message": "Ticket disputed successfully"}


@router.post("/topup/")
def topup_balance(
        amount: float,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    current_user.balance += amount
    db.commit()
    db.refresh(current_user)
    return {"message": "Balance updated", "new_balance": current_user.balance}


@router.get("/tolls/", response_model=List[schemas.TollTransaction])
def get_toll_transactions(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    return crud.get_user_toll_transactions(db, user_id=current_user.id)


@router.post("/park/", response_model=schemas.ParkingSession)
async def start_parking_session(
        zone: str = Form(..., description="Parking zone"),
        vehicle_plate: str = Form(..., description="Vehicle plate number"),
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Start a new parking session with loan-based payment availability

    Form fields:
    - zone: Parking zone (required)
    - vehicle_plate: Vehicle plate number (required)
    """
    # Check if vehicle exists and belongs to user
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == vehicle_plate,
        models.Vehicle.user_id == current_user.id
    ).first()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found or doesn't belong to user")

    # Check parking affordability (considering loan availability)
    parking_rate = 2.0  # Example rate per hour
    estimated_cost = parking_rate  # Initial cost

    can_afford, affordability_message = crud.check_parking_affordability(
        db, current_user.id, estimated_cost
    )

    if not can_afford:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start parking session: {affordability_message}"
        )

    # Create parking session
    try:
        db_session = models.ParkingSession(
            zone=zone,
            vehicle_plate=vehicle_plate,
            start_time=datetime.utcnow(),
            end_time=None,
            amount=0.0,  # Set initial amount to 0, will be calculated when session ends
            is_paid=False,  # Will be marked as paid when session ends and payment is processed
            user_id=current_user.id,
            vehicle_id=vehicle.id
        )

        db.add(db_session)
        db.commit()
        db.refresh(db_session)

        return db_session

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating parking session: {str(e)}"
        )


@router.post("/park/end/{session_id}", response_model=schemas.ParkingSession)
async def end_parking_session(
        session_id: int,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    End a parking session and process payment automatically
    """
    # Get parking session
    parking_session = db.query(models.ParkingSession).filter(
        models.ParkingSession.id == session_id,
        models.ParkingSession.user_id == current_user.id,
        models.ParkingSession.end_time == None  # Only active sessions
    ).first()

    if not parking_session:
        raise HTTPException(status_code=404, detail="Active parking session not found")

    # Calculate parking cost
    parking_rate = 2.0  # $2 per hour
    start_time = parking_session.start_time
    end_time = datetime.utcnow()
    duration_hours = (end_time - start_time).total_seconds() / 3600

    # Minimum charge for 1 hour, then hourly rate
    if duration_hours <= 1:
        amount = parking_rate
    else:
        amount = round(parking_rate * duration_hours, 2)

    # Process payment with loan fallback
    payment_success, used_loan, payment_message = crud.process_parking_payment(
        db, current_user.id, amount,
        f"Parking in {parking_session.zone} for {duration_hours:.1f} hours"
    )

    if not payment_success:
        raise HTTPException(
            status_code=400,
            detail=f"Could not process parking payment: {payment_message}"
        )

    # Update parking session
    try:
        parking_session.end_time = end_time
        parking_session.amount = amount
        parking_session.is_paid = True

        db.commit()
        db.refresh(parking_session)

        # Add payment info to response
        parking_session.payment_message = payment_message
        parking_session.used_loan = used_loan

        return parking_session

    except Exception as e:
        db.rollback()
        # If session update fails, refund the payment
        try:
            if used_loan:
                # Reverse the loan transaction
                crud.update_user_balance(db, current_user.id, amount, "repayment")
            else:
                # Refund the deducted balance
                crud.update_user_balance(db, current_user.id, amount, "deposit")
        except:
            pass  # If refund fails, at least we tried

        raise HTTPException(
            status_code=500,
            detail=f"Error ending parking session: {str(e)}"
        )


@router.get("/park/active", response_model=List[schemas.ParkingSession])
async def get_active_parking_sessions(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get user's active parking sessions
    """
    active_sessions = db.query(models.ParkingSession).filter(
        models.ParkingSession.user_id == current_user.id,
        models.ParkingSession.end_time == None
    ).all()

    return active_sessions


@router.get("/park/estimate")
async def estimate_parking_cost(
        zone: str,
        duration_hours: float = Query(..., gt=0, description="Estimated parking duration in hours"),
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Estimate parking cost and check affordability
    """
    parking_rate = 2.0  # $2 per hour
    estimated_cost = round(parking_rate * max(1, duration_hours), 2)

    can_afford, affordability_message = crud.check_parking_affordability(
        db, current_user.id, estimated_cost
    )

    return {
        "zone": zone,
        "estimated_duration_hours": duration_hours,
        "estimated_cost": estimated_cost,
        "can_afford": can_afford,
        "affordability_message": affordability_message,
        "parking_rate_per_hour": parking_rate
    }


@router.get("/tolls/transactions/", response_model=List[schemas.TollTransaction])
def get_toll_transactions(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    return db.query(models.TollTransaction).filter(
        models.TollTransaction.user_id == current_user.id
    ).order_by(models.TollTransaction.timestamp.desc()).all()


@router.get("/tolls/keypasses/", response_model=List[schemas.TollKeypass])
def get_user_keypasses(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    return db.query(models.TollKeypass).filter(
        models.TollKeypass.user_id == current_user.id
    ).all()


@router.post("/loan/repay-manual", response_model=schemas.LoanTransaction)
async def manual_loan_repayment(
        repayment_request: schemas.RepaymentRequest,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Manually repay loan from available balance"""
    try:
        balance = crud.get_user_balance(db, current_user.id)

        if not balance or balance.loan_balance <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No outstanding loan to repay"
            )

        if repayment_request.amount > balance.loan_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repayment amount exceeds loan balance"
            )

        if repayment_request.amount > balance.available_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient available balance for repayment"
            )

        # Update balance - deduct from available and reduce loan
        balance.available_balance -= repayment_request.amount
        balance.loan_balance -= repayment_request.amount
        balance.total_balance = balance.available_balance - balance.loan_balance
        balance.last_updated = datetime.utcnow()

        # Create transaction record
        transaction = crud.create_loan_transaction(
            db, current_user.id, repayment_request.amount, "manual_repayment",
            "Manual loan repayment from available balance"
        )

        db.commit()
        db.refresh(balance)

        return transaction

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/cash/load/preview", response_model=schemas.LoanDeductionDetail)
async def preview_cash_load(
        load_request: schemas.CashLoadRequest,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Preview how cash load will be allocated between loan and available balance"""
    try:
        target_user_id = load_request.user_id if load_request.user_id else current_user.id

        balance = crud.get_user_balance(db, target_user_id)
        if not balance:
            balance = crud.create_user_balance(db, target_user_id)

        # Calculate how the deposit would be allocated
        if balance.loan_balance <= 0:
            # No loan to deduct from
            return {
                "original_deposit": load_request.amount,
                "loan_paid": 0.0,
                "interest_paid": 0.0,
                "remaining_balance": load_request.amount,
                "new_available_balance": balance.available_balance + load_request.amount,
                "new_loan_balance": balance.loan_balance
            }

        # Calculate deduction
        loan_paid = min(load_request.amount, balance.loan_balance)
        remaining = load_request.amount - loan_paid

        return {
            "original_deposit": load_request.amount,
            "loan_paid": loan_paid,
            "interest_paid": 0.0,  # Interest is already included in loan_balance
            "remaining_balance": remaining,
            "new_available_balance": balance.available_balance + remaining,
            "new_loan_balance": balance.loan_balance - loan_paid
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# In routers/users.py
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
