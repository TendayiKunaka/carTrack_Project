from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import crud, schemas, models
from datetime import datetime, date, time, timedelta
from auth import get_current_user, get_db, pwd_context, get_current_parking_worker

router = APIRouter(prefix="/borrow", tags=["borrow"])


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


@router.get("/balance", response_model=schemas.UserBalance)
async def get_my_balance(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get current user's balance information"""
    balance = crud.get_user_balance(db, current_user.id)
    if not balance:
        balance = crud.create_user_balance(db, current_user.id)
    return balance


@router.get("/transactions", response_model=List[schemas.LoanTransaction])
async def get_my_loan_transactions(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get user's loan transaction history"""
    return db.query(models.LoanTransaction).filter(
        models.LoanTransaction.user_id == current_user.id
    ).order_by(models.LoanTransaction.timestamp.desc()).all()


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


# Add to routers/borrow.py

@router.get("/customer/balance", response_model=schemas.CustomerBalanceResponse)
async def get_customer_balance(
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get customer balance information (for admin/staff use)"""
    # In a real app, you'd add authorization checks here
    # For example: if not current_user.is_staff: raise HTTPException(...)

    customer = crud.get_customer_by_identifier(db, user_id, username, email)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    balance = crud.get_user_balance(db, customer.id)
    if not balance:
        balance = crud.create_user_balance(db, customer.id)

    remaining_limit = max(0.0, 20.0 - balance.loan_balance)

    return {
        "user_id": customer.id,
        "username": customer.username,
        "full_name": customer.full_name,
        "email": customer.email,
        "available_balance": balance.available_balance,
        "loan_balance": balance.loan_balance,
        "total_balance": balance.total_balance,
        "last_updated": balance.last_updated,
        "can_borrow_more": balance.loan_balance < 20.0,
        "remaining_borrow_limit": remaining_limit
    }


@router.get("/customer/transactions", response_model=List[schemas.CustomerTransactionResponse])
async def get_customer_transactions(
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        limit: int = 100,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get customer's loan transactions (for admin/staff use)"""
    customer = crud.get_customer_by_identifier(db, user_id, username, email)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    transactions = crud.get_customer_transactions(db, customer.id, limit)

    # Format response with user information
    response = []
    for transaction in transactions:
        response.append({
            "id": transaction.id,
            "user_id": transaction.user_id,
            "username": customer.username,
            "full_name": customer.full_name,
            "amount": transaction.amount,
            "transaction_type": transaction.transaction_type,
            "description": transaction.description,
            "timestamp": transaction.timestamp,
            "interest_applied": transaction.interest_applied
        })

    return response


@router.get("/customers/balances", response_model=List[schemas.CustomerBalanceResponse])
async def get_all_customers_balances(
        skip: int = 0,
        limit: int = 100,
        min_balance: Optional[float] = None,
        max_balance: Optional[float] = None,
        has_loan: Optional[bool] = None,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get balances for all customers (for admin/staff use)"""
    if has_loan is not None or min_balance is not None or max_balance is not None:
        balances = crud.search_customers_by_balance(
            db, min_balance, max_balance, has_loan, skip, limit
        )
    else:
        balances = crud.get_all_customers_balances(db, skip, limit)

    response = []
    for balance in balances:
        customer = balance.user
        remaining_limit = max(0.0, 20.0 - balance.loan_balance)

        response.append({
            "user_id": customer.id,
            "username": customer.username,
            "full_name": customer.full_name,
            "email": customer.email,
            "available_balance": balance.available_balance,
            "loan_balance": balance.loan_balance,
            "total_balance": balance.total_balance,
            "last_updated": balance.last_updated,
            "can_borrow_more": balance.loan_balance < 20.0,
            "remaining_borrow_limit": remaining_limit
        })

    return response


@router.get("/customer/{user_id}/balance", response_model=schemas.CustomerBalanceResponse)
async def get_customer_balance_by_id(
        user_id: int,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get customer balance by user ID"""
    customer = crud.get_customer_by_identifier(db, user_id=user_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    balance = crud.get_user_balance(db, customer.id)
    if not balance:
        balance = crud.create_user_balance(db, customer.id)

    remaining_limit = max(0.0, 20.0 - balance.loan_balance)

    return {
        "user_id": customer.id,
        "username": customer.username,
        "full_name": customer.full_name,
        "email": customer.email,
        "available_balance": balance.available_balance,
        "loan_balance": balance.loan_balance,
        "total_balance": balance.total_balance,
        "last_updated": balance.last_updated,
        "can_borrow_more": balance.loan_balance < 20.0,
        "remaining_borrow_limit": remaining_limit
    }


@router.post("/cash/load", response_model=schemas.CashLoadResponse)
async def load_cash(
        load_request: schemas.CashLoadRequest,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Load cash to user's available balance with automatic loan deduction"""
    try:
        # Determine which user to load cash for
        target_user_id = load_request.user_id if load_request.user_id else current_user.id

        # Check if admin is loading for another user
        if load_request.user_id and load_request.user_id != current_user.id:
            # Add admin authorization check here if needed
            # if not current_user.is_admin: raise HTTPException(...)
            pass

        # Use the new function with auto-deduction
        transaction, balance, loan_paid, interest_paid = crud.load_cash_to_balance_with_auto_deduction(
            db, target_user_id, load_request.amount, load_request.description
        )

        message = f"Successfully loaded ${load_request.amount}"
        if loan_paid > 0:
            message += f". ${loan_paid} was automatically deducted to pay down your loan"
        if interest_paid > 0:
            message += f" (including ${interest_paid} interest)"

        return {
            "transaction": transaction,
            "new_balance": balance,
            "loan_paid": loan_paid,
            "interest_paid": interest_paid,
            "message": message
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/cash/withdraw", response_model=schemas.CashLoadResponse)
async def withdraw_cash(
        load_request: schemas.CashLoadRequest,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Withdraw cash from available balance"""
    try:
        # Users can only withdraw their own balance
        transaction, balance = crud.withdraw_cash(
            db, current_user.id, load_request.amount, load_request.description
        )

        return {
            "transaction": transaction,
            "new_balance": balance,
            "message": f"Successfully withdrew ${load_request.amount} from balance"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/cash/transfer", response_model=dict)
async def transfer_balance(
        transfer_request: schemas.CashTransferRequest,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Transfer balance to another user"""
    try:
        if transfer_request.target_user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot transfer to yourself"
            )

        from_transaction, to_transaction, from_balance, to_balance = crud.transfer_balance(
            db, current_user.id, transfer_request.target_user_id,
            transfer_request.amount, transfer_request.description
        )

        return {
            "message": f"Successfully transferred ${transfer_request.amount} to user {transfer_request.target_user_id}",
            "from_transaction": from_transaction,
            "to_transaction": to_transaction,
            "your_new_balance": from_balance,
            "recipient_new_balance": to_balance
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/admin/cash/load", response_model=schemas.CashLoadResponse)
async def admin_load_cash(
        load_request: schemas.CashLoadRequest,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Admin endpoint to load cash to any user's balance with auto loan deduction"""
    # Add admin authorization check here
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    if not load_request.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required for admin cash load"
        )

    try:
        # Use the new function with auto-deduction
        transaction, balance, loan_paid, interest_paid = crud.load_cash_to_balance_with_auto_deduction(
            db, load_request.user_id, load_request.amount,
            f"Admin deposit: {load_request.description}"
        )

        # Get user info for response
        target_user = crud.get_customer_by_identifier(db, user_id=load_request.user_id)

        message = f"Successfully loaded ${load_request.amount} to {target_user.username}'s balance"
        if loan_paid > 0:
            message += f". ${loan_paid} was automatically deducted to pay down their loan"
        if interest_paid > 0:
            message += f" (including ${interest_paid} interest)"

        return {
            "transaction": transaction,
            "new_balance": balance,
            "loan_paid": loan_paid,
            "interest_paid": interest_paid,
            "message": message
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
