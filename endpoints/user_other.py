from fastapi import APIRouter, Depends, HTTPException, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from starlette import status

import crud
import models
import schemas
from auth import get_current_user, get_db, get_current_registry_worker, pwd_context

router = APIRouter(prefix="/user", tags=["users_ignore"])


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
