from fastapi import APIRouter, Depends, HTTPException, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from starlette import status
import crud
import models
import schemas
from auth import get_current_user, get_db, get_current_registry_worker, pwd_context

router = APIRouter(prefix="/user", tags=["users_car_management"])


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


@router.get("/tolls/", response_model=List[schemas.TollTransaction])
def get_toll_transactions(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    return crud.get_user_toll_transactions(db, user_id=current_user.id)


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
