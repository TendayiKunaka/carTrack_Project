from datetime import datetime, timedelta  # Correct import

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
import secrets
import string

import crud
import models
import schemas
from auth import get_current_user, get_db

router = APIRouter(prefix="/tolls", tags=["tolls"])


# Helper function to generate keypass code
def generate_keypass_code(length=12):
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


@router.get("/gates/", response_model=List[schemas.TollGate])
def get_toll_gates(db: Session = Depends(get_db)):
    """
    Get all toll gates
    """
    return db.query(models.TollGate).all()


@router.get("/routes/", response_model=List[schemas.TollRoute])
def get_toll_routes(db: Session = Depends(get_db)):
    # Eager load the relationships to calculate total_amount
    routes = db.query(models.TollRoute).options(
        joinedload(models.TollRoute.toll_gates).joinedload(models.TollGateRoute.toll_gate)
    ).all()
    return routes


@router.post("/keypass/buy/", response_model=schemas.TollKeypass)
def buy_toll_keypass(
        keypass: schemas.TollKeypassCreate,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Check if vehicle exists and belongs to user (if specified)
    vehicle = None
    if keypass.vehicle_plate:
        vehicle = crud.get_vehicle(db, keypass.vehicle_plate)
        if not vehicle or vehicle.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found or doesn't belong to user"
            )

    # Process payment with loan fallback
    payment_success, used_loan, payment_message = crud.process_toll_payment(
        db, current_user.id, keypass.amount, f"Keypass purchase: ${keypass.amount}"
    )

    if not payment_success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=payment_message
        )

    # Create keypass - FIXED: use datetime.utcnow() instead of datetime.datetime.utcnow()
    db_keypass = models.TollKeypass(
        code=generate_keypass_code(),
        amount=keypass.amount,
        balance=keypass.amount,
        expires_at=datetime.utcnow() + timedelta(days=keypass.expires_in_days),  # FIXED
        user_id=current_user.id,
        vehicle_id=vehicle.id if vehicle else None
    )

    db.add(db_keypass)
    db.commit()
    db.refresh(db_keypass)

    # Add payment info to response
    db_keypass.payment_message = payment_message
    db_keypass.used_loan = used_loan

    return db_keypass


@router.post("/pay/", response_model=schemas.TollPaymentResponse)  # Changed response model
def pay_toll(
        toll: schemas.TollTransactionCreate,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Get vehicle
    vehicle = crud.get_vehicle(db, toll.vehicle_plate)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )

    # Get toll gate or route
    if toll.toll_gate_id:
        toll_gate = db.query(models.TollGate).filter(models.TollGate.id == toll.toll_gate_id).first()
        if not toll_gate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Toll gate not found"
            )
        amount = toll_gate.amount
        route_id = None
        toll_gate_id = toll.toll_gate_id
        description = f"Toll gate: {toll_gate.name}"
    elif toll.route_id:
        route = db.query(models.TollRoute).filter(models.TollRoute.id == toll.route_id).first()
        if not route:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Route not found"
            )
        # Calculate total amount for the route
        amount = sum(tg.toll_gate.amount for tg in route.toll_gates)
        route_id = route.id
        toll_gate_id = None
        description = f"Route: {route.name}"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either toll_gate_id or route_id must be provided"
        )

    # Handle different payment methods
    if toll.payment_method == "cash":
        # Cash payment - just record the transaction
        db_transaction = models.TollTransaction(
            amount=amount,
            toll_gate_id=toll_gate_id,
            route_id=route_id,
            user_id=current_user.id,
            vehicle_id=vehicle.id,
            payment_method="cash",
            status="completed"
        )

        payment_success = True
        used_loan = False
        payment_message = "Cash payment successful"

    elif toll.payment_method == "balance":
        # Process payment with loan fallback
        payment_success, used_loan, payment_message = crud.process_toll_payment(
            db, current_user.id, amount, description
        )

        if not payment_success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=payment_message
            )

        db_transaction = models.TollTransaction(
            amount=amount,
            toll_gate_id=toll_gate_id,
            route_id=route_id,
            user_id=current_user.id,
            vehicle_id=vehicle.id,
            payment_method="balance",
            status="completed"
        )

    elif toll.payment_method == "keypass":
        if not toll.keypass_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Keypass code required for keypass payment"
            )

        # Get and validate keypass - FIXED: use datetime.utcnow() instead of datetime.datetime.utcnow()
        keypass = db.query(models.TollKeypass).filter(
            models.TollKeypass.code == toll.keypass_code,
            models.TollKeypass.is_active == True,
            models.TollKeypass.expires_at > datetime.utcnow()  # FIXED
        ).first()

        if not keypass:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired keypass"
            )

        if keypass.balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient keypass balance"
            )

        # Deduct from keypass
        keypass.balance -= amount

        db_transaction = models.TollTransaction(
            amount=amount,
            toll_gate_id=toll_gate_id,
            route_id=route_id,
            user_id=current_user.id,
            vehicle_id=vehicle.id,
            payment_method="keypass",
            keypass_id=keypass.id,
            status="completed"
        )

        payment_success = True
        used_loan = False
        payment_message = "Keypass payment successful"

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment method"
        )

    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    # Get updated balance if payment was from balance
    new_balance = None
    if toll.payment_method == "balance":
        balance = crud.get_user_balance(db, current_user.id)
        new_balance = balance.total_balance if balance else 0.0

    # Get keypass balance if payment was from keypass
    keypass_balance = None
    if toll.payment_method == "keypass":
        keypass_balance = keypass.balance

    return {
        "transaction": db_transaction,
        "new_balance": new_balance,
        "keypass_balance": keypass_balance,
        "payment_message": payment_message,
        "used_loan": used_loan
    }


@router.post("/pay-route/", response_model=List[schemas.TollPaymentResponse])
def pay_entire_route(
        route_payment: schemas.RoutePaymentCreate,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Pay for all toll gates on a specific route at once with auto-deduction
    """
    # Get route and its toll gates
    route = db.query(models.TollRoute).filter(models.TollRoute.id == route_payment.route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route not found"
        )

    # Get vehicle
    vehicle = crud.get_vehicle(db, route_payment.vehicle_plate)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )

    transactions = []

    for toll_gate_route in route.toll_gates:
        toll_gate = toll_gate_route.toll_gate

        # Create transaction for each toll gate
        transaction_data = schemas.TollTransactionCreate(
            vehicle_plate=route_payment.vehicle_plate,
            toll_gate_id=toll_gate.id,
            payment_method=route_payment.payment_method,
            keypass_code=route_payment.keypass_code
        )

        # Use the modified pay_toll function
        result = pay_toll(transaction_data, current_user, db)
        transactions.append(result)

    return transactions


@router.get("/keypass/", response_model=List[schemas.TollKeypass])
def get_user_keypasses(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    return db.query(models.TollKeypass).filter(
        models.TollKeypass.user_id == current_user.id
    ).all()


# ADDITIONAL ENDPOINTS FOR BETTER FUNCTIONALITY

@router.get("/gates/{gate_id}", response_model=schemas.TollGate)
def get_toll_gate(gate_id: int, db: Session = Depends(get_db)):
    """
    Get a specific toll gate by ID
    """
    toll_gate = db.query(models.TollGate).filter(models.TollGate.id == gate_id).first()
    if not toll_gate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Toll gate not found"
        )
    return toll_gate


@router.get("/routes/{route_id}", response_model=schemas.TollRoute)
def get_toll_route(route_id: int, db: Session = Depends(get_db)):
    """
    Get a specific toll route by ID with all gates
    """
    route = db.query(models.TollRoute).filter(models.TollRoute.id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Toll route not found"
        )
    return route


@router.get("/keypass/{keypass_code}", response_model=schemas.TollKeypass)
def get_keypass(
        keypass_code: str,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get a specific keypass by code (only accessible by owner)
    """
    keypass = db.query(models.TollKeypass).filter(
        models.TollKeypass.code == keypass_code,
        models.TollKeypass.user_id == current_user.id
    ).first()

    if not keypass:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keypass not found or access denied"
        )
    return keypass
