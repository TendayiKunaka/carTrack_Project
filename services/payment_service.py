from datetime import datetime
from sqlalchemy.orm import Session
import crud


def process_payment(db: Session, user_id: int, amount: float, payment_method: str):
    """Process payment using different payment methods"""
    balance = crud.get_user_balance(db, user_id)
    if not balance:
        raise ValueError("User balance not found")

    if payment_method == "loan":
        # Check if user has available borrowed funds
        available_borrowed = balance.borrowed_amount - balance.used_borrowed_amount
        if amount > available_borrowed:
            raise ValueError("Insufficient borrowed funds available")

        # Mark the amount as used
        crud.update_borrowed_usage(db, user_id, amount)
        return True

    elif payment_method == "balance":
        # Normal balance deduction
        if amount > balance.available_balance:
            raise ValueError("Insufficient available balance")

        balance.available_balance -= amount
        balance.total_balance = balance.available_balance - balance.loan_balance
        balance.last_updated = datetime.utcnow()
        db.commit()
        return True

    elif payment_method == "cash":
        # Cash payments don't affect digital balance
        return True

    elif payment_method == "keypass":
        # Handle keypass payment (you'll need to implement this)
        # For now, just return True as placeholder
        return True

    return False
