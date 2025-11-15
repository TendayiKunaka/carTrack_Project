from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import crud, schemas, models
from datetime import datetime, date, time, timedelta
from auth import get_current_user, get_db, pwd_context, get_current_parking_worker

router = APIRouter(prefix="/borrow", tags=["user_loan"])


# In your borrow router, update these endpoints

@router.post("/request", response_model=schemas.LoanTransaction)
async def borrow_money(
        borrow_request: schemas.BorrowRequest,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Borrow money from the system"""
    if not crud.can_borrow_more(db, current_user.id, borrow_request.amount):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot borrow more than $20 total"
        )

    # Update balance - only track the borrowed amount, don't add to available yet
    balance = crud.update_user_balance(db, current_user.id, borrow_request.amount, "borrow")

    # Create transaction record
    transaction = crud.create_loan_transaction(
        db, current_user.id, borrow_request.amount, "borrow",
        f"Cash loan for: {borrow_request.purpose}"
    )

    return transaction

@router.post("/use", response_model=schemas.LoanTransaction)
async def use_borrowed_money(
        use_request: schemas.BorrowRequest,  # Reuse the same schema
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Mark borrowed money as used (for actual spending)"""
    balance = crud.get_user_balance(db, current_user.id)
    if not balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No balance record found"
        )

    # Check if user has enough available borrowed money
    available_borrowed = balance.borrowed_amount - balance.used_borrowed_amount
    if use_request.amount > available_borrowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only ${available_borrowed:.2f} available from borrowed funds"
        )

    # Mark the amount as used
    crud.update_borrowed_usage(db, current_user.id, use_request.amount)

    # Create transaction record
    transaction = crud.create_loan_transaction(
        db, current_user.id, use_request.amount, "use",
        f"Used borrowed funds for: {use_request.purpose}"
    )

    return transaction

@router.post("/repay", response_model=schemas.LoanTransaction)
async def repay_loan(
        repayment_request: schemas.RepaymentRequest,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Repay borrowed money"""
    balance = crud.get_user_balance(db, current_user.id)

    if not balance or balance.loan_balance <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No outstanding loan to repay"
        )

    if repayment_request.amount > balance.available_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient available balance for repayment"
        )

    # Calculate how much of the repayment goes to principal vs interest
    total_owed = balance.used_borrowed_amount * 1.25
    if repayment_request.amount > total_owed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repayment amount exceeds total owed (${total_owed:.2f})"
        )

    # Apply repayment
    interest_paid = repayment_request.amount - (repayment_request.amount / 1.25)
    principal_repaid = repayment_request.amount - interest_paid

    balance.available_balance -= repayment_request.amount
    balance.used_borrowed_amount = max(0, balance.used_borrowed_amount - principal_repaid)
    balance.loan_balance = max(0, balance.borrowed_amount - balance.used_borrowed_amount) * 1.25
    balance.total_balance = balance.available_balance - balance.loan_balance
    balance.last_updated = datetime.utcnow()

    # Create transaction record
    transaction = crud.create_loan_transaction(
        db, current_user.id, repayment_request.amount, "repayment",
        f"Loan repayment (${principal_repaid:.2f} principal + ${interest_paid:.2f} interest)"
    )

    db.commit()
    db.refresh(balance)

    return transaction


@router.get("/limit")
async def get_borrow_limit(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get user's remaining borrowing capacity"""
    balance = crud.get_user_balance(db, current_user.id)
    if not balance:
        return {"remaining_limit": 20.0, "current_loan": 0.0}

    remaining = 20.0 - balance.loan_balance
    return {
        "remaining_limit": max(0.0, remaining),
        "current_loan": balance.loan_balance
    }
