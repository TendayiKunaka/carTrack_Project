from operator import or_

from sqlalchemy.orm import Session
import models
import schemas, schemas_accident
from datetime import datetime, timedelta
from auth import pwd_context, get_password_hash


# Update your create_user function
def create_user(db: Session, user: schemas.UserCreate):
    # Check if user already exists
    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()
    if db_user:
        return None

    # Hash the password
    hashed_password = pwd_context.hash(user.password)

    # Create user object
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        phone_number=user.phone_number,
        address=user.address,
        town=user.town,
        city=user.city
    )

    # Add to database
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


'''def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()'''


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def get_parking_worker_by_username(db: Session, username: str):
    return db.query(models.ParkingWorker).filter(models.ParkingWorker.username == username).first()


def get_police_by_username(db: Session, username: str):
    return db.query(models.Police).filter(models.Police.username == username).first()


def get_registry_by_username(db: Session, username: str):
    return db.query(models.RegistryWorker).filter(models.RegistryWorker.username == username).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


'''def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        phone_number=user.phone_number
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user'''


# Vehicle operations
def get_vehicle(db: Session, plate_number: str):
    return db.query(models.Vehicle).filter(models.Vehicle.plate_number == plate_number).first()


def create_vehicle(db: Session, vehicle: schemas.VehicleCreate, user_id: int):
    db_vehicle = models.Vehicle(
        plate_number=vehicle.plate_number,
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        color=vehicle.color,
        mileage_at_import=vehicle.mileage_at_import,
        road_worthiness_expiry=vehicle.road_worthiness_expiry,
        user_id=user_id
    )
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


def get_user_vehicles(db: Session, user_id: int):
    return db.query(models.Vehicle).filter(models.Vehicle.user_id == user_id).all()


# Ticket operations
def create_ticket(db: Session, ticket: schemas.TicketCreate, officer_id: int):
    vehicle = get_vehicle(db, ticket.vehicle_plate)
    if not vehicle:
        return None

    due_date = datetime.utcnow() + timedelta(days=30)

    db_ticket = models.Ticket(
        violation_type=ticket.violation_type,
        amount=ticket.amount,
        due_date=due_date,
        photo_url=ticket.photo_url,
        location=ticket.location,
        user_id=vehicle.user_id,
        vehicle_id=vehicle.id,
        officer_id=officer_id
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket


def get_user_tickets(db: Session, user_id: int):
    return db.query(models.Ticket).filter(models.Ticket.user_id == user_id).all()


def dispute_ticket(db: Session, ticket_id: int):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if db_ticket:
        db_ticket.is_disputed = True
        db.commit()
        db.refresh(db_ticket)
    return db_ticket


# Parking operations
def start_parking_session(db: Session, parking: schemas.ParkingSessionCreate, user_id: int):
    vehicle = get_vehicle(db, parking.vehicle_plate)
    if not vehicle:
        return None

    db_parking = models.ParkingSession(
        zone=parking.zone,
        user_id=user_id,
        vehicle_id=vehicle.id
    )
    db.add(db_parking)
    db.commit()
    db.refresh(db_parking)
    return db_parking


def end_parking_session(db: Session, session_id: int, amount: float):
    db_parking = db.query(models.ParkingSession).filter(models.ParkingSession.id == session_id).first()
    if db_parking:
        db_parking.end_time = datetime.utcnow()
        db_parking.amount = amount
        db.commit()
        db.refresh(db_parking)
    return db_parking


# Toll operations
def create_toll_transaction(db: Session, toll: schemas.TollTransactionCreate, user_id: int):
    vehicle = get_vehicle(db, toll.vehicle_plate)
    if not vehicle:
        return None

    toll_gate = db.query(models.TollGate).filter(models.TollGate.id == toll.toll_gate_id).first()
    if not toll_gate:
        return None

    db_toll = models.TollTransaction(
        amount=toll_gate.amount,
        toll_gate_id=toll.toll_gate_id,
        user_id=user_id,
        vehicle_id=vehicle.id
    )
    db.add(db_toll)
    db.commit()
    db.refresh(db_toll)
    return db_toll


def get_user_toll_transactions(db: Session, user_id: int):
    return db.query(models.TollTransaction).filter(models.TollTransaction.user_id == user_id).all()


# Vehicle history operations
def create_accident_record(db: Session, accident: schemas.AccidentCreate):
    vehicle = get_vehicle(db, accident.vehicle_plate)
    if not vehicle:
        return None

    db_accident = models.Accident(
        date=accident.date,
        description=accident.description,
        severity=accident.severity,
        vehicle_id=vehicle.id
    )
    db.add(db_accident)
    db.commit()
    db.refresh(db_accident)
    return db_accident


def get_vehicle_history(db: Session, plate_number: str):
    vehicle = get_vehicle(db, plate_number)
    if not vehicle:
        return None

    return {
        "vehicle": vehicle,
        "accidents": db.query(models.Accident).filter(models.Accident.vehicle_id == vehicle.id).all(),
        "ownership_history": db.query(models.OwnershipHistory).filter(
            models.OwnershipHistory.vehicle_id == vehicle.id).all()
    }


# Update your create_user function
def create_parking_worker(db: Session, worker: schemas.ParkingWorkerCreate):
    # Check if user already exists
    db_user = db.query(models.User).filter(
        models.ParkingWorker.username == worker.username
    ).first()
    if db_user:
        return None

    # Hash the password
    hashed_password = pwd_context.hash(worker.password)

    # Create user object
    db_worker = models.ParkingWorker(
        username=worker.username,
        employee_id=worker.employee_id,
        zone=worker.zone,
        full_name=worker.full_name,
        hashed_password=get_password_hash(worker.password)  # If you have password hashing
    )
    # Add to database
    db.add(db_worker)
    db.commit()
    db.refresh(db_worker)
    return db_worker


def get_tickets_by_zone(db: Session, zone: str, skip: int = 0, limit: int = 100):
    return db.query(models.Ticket).filter(
        models.Ticket.location == zone
    ).offset(skip).limit(limit).all()


def search_tickets(db: Session, search_term: str, zone: str):
    return db.query(models.Ticket).join(models.Vehicle).filter(
        models.Ticket.location == zone,
        or_(
            models.Vehicle.plate_number.ilike(f"%{search_term}%"),
            models.Ticket.violation_type.ilike(f"%{search_term}%"),
            models.Ticket.location.ilike(f"%{search_term}%")
        )
    ).all()


def get_ticket_by_id(db: Session, ticket_id: int):
    return db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()


def create_police(db: Session, police: schemas.PoliceCreate):
    # Check if police officer already exists
    db_police = db.query(models.Police).filter(
        (models.Police.username == police.username) |
        (models.Police.badge_number == police.badge_number)
    ).first()
    if db_police:
        return None  # Officer already exists

    # Hash the password
    hashed_password = pwd_context.hash(police.password)

    # Create police object
    db_police = models.Police(
        badge_number=police.badge_number,
        username=police.username,
        hashed_password=hashed_password,
        full_name=police.full_name,
        station=police.station
    )

    # Add to database
    db.add(db_police)
    db.commit()
    db.refresh(db_police)
    return db_police


def get_registry_worker_by_username(db: Session, username: str):
    """Get a registry worker by username"""
    return db.query(models.RegistryWorker).filter(models.RegistryWorker.username == username).first()


def create_registry_worker(db: Session, worker: schemas.RegistryWorkerCreate):
    """Create a new registry worker"""
    # Check if worker already exists
    db_worker = db.query(models.RegistryWorker).filter(
        (models.RegistryWorker.username == worker.username) |
        (models.RegistryWorker.employee_id == worker.employee_id)
    ).first()
    if db_worker:
        return None  # Worker already exists

    # Hash the password
    hashed_password = pwd_context.hash(worker.password)

    # Create worker object
    db_worker = models.RegistryWorker(
        employee_id=worker.employee_id,
        username=worker.username,
        hashed_password=hashed_password,
        full_name=worker.full_name
    )

    # Add to database
    db.add(db_worker)
    db.commit()
    db.refresh(db_worker)
    return db_worker


# In crud.py, add these functions

def process_toll_payment(db: Session, user_id: int, amount: float, description: str):
    """
    Process toll payment with automatic loan fallback
    Returns: (success, used_loan, message)
    """
    balance = get_user_balance(db, user_id)
    if not balance:
        balance = create_user_balance(db, user_id)

    # First try to pay from available balance
    if balance.available_balance >= amount:
        balance.available_balance -= amount
        balance.total_balance = balance.available_balance - balance.loan_balance
        balance.last_updated = datetime.utcnow()

        # Create transaction record
        create_loan_transaction(
            db, user_id, amount, "payment",
            f"{description} - Paid from balance"
        )

        db.commit()
        return True, False, "Payment successful from available balance"

    # If not enough balance, check if we can use loan
    available_borrowed = balance.borrowed_amount - balance.used_borrowed_amount
    if available_borrowed >= amount:
        # Mark the amount as used from borrowed funds
        balance.used_borrowed_amount += amount
        balance.loan_balance = max(0, balance.borrowed_amount - balance.used_borrowed_amount) * 1.25
        balance.total_balance = balance.available_balance - balance.loan_balance
        balance.last_updated = datetime.utcnow()

        # Create transaction record
        create_loan_transaction(
            db, user_id, amount, "payment",
            f"{description} - Paid from borrowed funds"
        )

        db.commit()
        return True, True, "Payment successful using borrowed funds"

    # If neither balance nor loan is sufficient
    return False, False, f"Insufficient funds. Available: ${balance.available_balance:.2f}, Loan available: ${available_borrowed:.2f}"


def get_vehicle(db: Session, plate_number: str):
    """Get vehicle by plate number"""
    return db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == plate_number
    ).first()


def create_loan_transaction(db: Session, user_id: int, amount: float,
                            transaction_type: str, description: str):
    """Create a loan transaction record"""
    db_transaction = models.LoanTransaction(
        user_id=user_id,
        amount=amount,
        transaction_type=transaction_type,
        description=description,
        timestamp=datetime.utcnow()
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


def get_user_balance(db: Session, user_id: int):
    """Get user balance record"""
    return db.query(models.UserBalance).filter(
        models.UserBalance.user_id == user_id
    ).first()


def create_user_balance(db: Session, user_id: int):
    """Create a new user balance record"""
    db_balance = models.UserBalance(
        user_id=user_id,
        available_balance=0.0,
        loan_balance=0.0,
        total_balance=0.0,
        borrowed_amount=0.0,
        used_borrowed_amount=0.0
    )
    db.add(db_balance)
    db.commit()
    db.refresh(db_balance)
    return db_balance


def update_user_balance(db: Session, user_id: int, amount: float, transaction_type: str):
    """Update user balance based on transaction type"""
    balance = get_user_balance(db, user_id)
    if not balance:
        balance = create_user_balance(db, user_id)

    if transaction_type == "deposit":
        balance.available_balance += amount
    elif transaction_type == "withdraw":
        balance.available_balance -= amount
    elif transaction_type == "borrow":
        balance.loan_balance += amount
        balance.total_balance = balance.available_balance - balance.loan_balance
    elif transaction_type == "repayment":
        balance.loan_balance -= amount
        balance.total_balance = balance.available_balance - balance.loan_balance

    balance.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(balance)
    return balance


def can_borrow_more(db: Session, user_id: int, amount: float) -> bool:
    """Check if user can borrow more money"""
    balance = get_user_balance(db, user_id)
    if not balance:
        return True  # New user can borrow

    # User can't borrow if loan balance is already -$20 or more
    if balance.loan_balance + amount > 20.0:
        return False
    return True


def apply_interest_to_loan(db: Session, user_id: int):
    """Apply $1 interest to user's loan balance"""
    balance = get_user_balance(db, user_id)
    if balance and balance.loan_balance > 0.01:  # Only apply interest if loan > 1 cent
        # Create interest transaction
        create_loan_transaction(
            db, user_id, 1.0, "interest", "Interest charge on outstanding loan"
        )

        # Update balance
        balance.loan_balance += 1.0
        balance.total_balance = balance.available_balance - balance.loan_balance
        balance.last_updated = datetime.utcnow()
        db.commit()
        db.refresh(balance)

        return True
    return False


def process_payment_with_loan_fallback(db: Session, user_id: int, amount: float,
                                       purpose: str, service_type: str):
    """
    Process payment with loan fallback
    Returns: (success: bool, used_loan: bool, message: str)
    """
    balance = get_user_balance(db, user_id)

    if not balance:
        balance = create_user_balance(db, user_id)

    # Try to use available balance first
    if balance.available_balance >= amount:
        # Sufficient balance
        update_user_balance(db, user_id, amount, "withdraw")
        create_loan_transaction(
            db, user_id, amount, "payment",
            f"Payment for {service_type}: {purpose}"
        )
        return True, False, "Payment successful from available balance"

    # Check if we can use loan
    remaining_amount = amount - balance.available_balance
    if can_borrow_more(db, user_id, remaining_amount):
        # Use all available balance and borrow the rest
        if balance.available_balance > 0:
            update_user_balance(db, user_id, balance.available_balance, "withdraw")

        # Borrow the remaining amount
        update_user_balance(db, user_id, remaining_amount, "borrow")
        create_loan_transaction(
            db, user_id, remaining_amount, "borrow",
            f"Loan for {service_type}: {purpose}"
        )

        # Apply interest immediately
        apply_interest_to_loan(db, user_id)

        return True, True, f"Payment successful. Used ${balance.available_balance} from balance and borrowed ${remaining_amount} "

    return False, False, "Insufficient balance and cannot borrow more (max $20 loan reached)"


def get_customer_balance(db: Session, user_id: int = None, username: str = None, email: str = None):
    """Get customer balance by user_id, username, or email"""
    query = db.query(models.UserBalance).join(models.User)

    if user_id:
        query = query.filter(models.User.id == user_id)
    elif username:
        query = query.filter(models.User.username == username)
    elif email:
        query = query.filter(models.User.email == email)
    else:
        return None

    return query.first()


def get_customer_by_identifier(db: Session, user_id: int = None, username: str = None, email: str = None):
    """Get customer by identifier"""
    query = db.query(models.User)

    if user_id:
        query = query.filter(models.User.id == user_id)
    elif username:
        query = query.filter(models.User.username == username)
    elif email:
        query = query.filter(models.User.email == email)
    else:
        return None

    return query.first()


def get_customer_transactions(db: Session, user_id: int, limit: int = 100):
    """Get customer's loan transactions"""
    return db.query(models.LoanTransaction).filter(
        models.LoanTransaction.user_id == user_id
    ).order_by(models.LoanTransaction.timestamp.desc()).limit(limit).all()


def get_all_customers_balances(db: Session, skip: int = 0, limit: int = 100):
    """Get balances for all customers"""
    return db.query(models.UserBalance).join(models.User).offset(skip).limit(limit).all()


def search_customers_by_balance(db: Session, min_balance: float = None, max_balance: float = None,
                                has_loan: bool = None, skip: int = 0, limit: int = 100):
    """Search customers by balance criteria"""
    query = db.query(models.UserBalance).join(models.User)

    if min_balance is not None:
        query = query.filter(models.UserBalance.total_balance >= min_balance)
    if max_balance is not None:
        query = query.filter(models.UserBalance.total_balance <= max_balance)
    if has_loan is not None:
        if has_loan:
            query = query.filter(models.UserBalance.loan_balance > 0)
        else:
            query = query.filter(models.UserBalance.loan_balance <= 0)

    return query.offset(skip).limit(limit).all()


# Add to crud.py

def load_cash_to_balance(db: Session, user_id: int, amount: float, description: str = "Cash deposit"):
    """Load cash to user's available balance"""
    if amount <= 0:
        raise ValueError("Amount must be positive")

    # Get or create balance record
    balance = get_user_balance(db, user_id)
    if not balance:
        balance = create_user_balance(db, user_id)

    # Update available balance
    balance.available_balance += amount
    balance.total_balance = balance.available_balance - balance.loan_balance
    balance.last_updated = datetime.utcnow()

    # Create transaction record
    transaction = create_loan_transaction(
        db, user_id, amount, "deposit", description
    )

    db.commit()
    db.refresh(balance)

    return transaction, balance


def transfer_balance(db: Session, from_user_id: int, to_user_id: int, amount: float,
                     description: str = "Balance transfer"):
    """Transfer balance between users"""
    if amount <= 0:
        raise ValueError("Amount must be positive")

    # Check sender's balance
    from_balance = get_user_balance(db, from_user_id)
    if not from_balance or from_balance.available_balance < amount:
        raise ValueError("Insufficient balance for transfer")

    # Get or create recipient's balance
    to_balance = get_user_balance(db, to_user_id)
    if not to_balance:
        to_balance = create_user_balance(db, to_user_id)

    # Perform transfer
    from_balance.available_balance -= amount
    from_balance.total_balance = from_balance.available_balance - from_balance.loan_balance
    from_balance.last_updated = datetime.utcnow()

    to_balance.available_balance += amount
    to_balance.total_balance = to_balance.available_balance - to_balance.loan_balance
    to_balance.last_updated = datetime.utcnow()

    # Create transaction records
    from_transaction = create_loan_transaction(
        db, from_user_id, amount, "transfer_out", f"Transfer to user {to_user_id}: {description}"
    )

    to_transaction = create_loan_transaction(
        db, to_user_id, amount, "transfer_in", f"Transfer from user {from_user_id}: {description}"
    )

    db.commit()
    db.refresh(from_balance)
    db.refresh(to_balance)

    return from_transaction, to_transaction, from_balance, to_balance


def withdraw_cash(db: Session, user_id: int, amount: float, description: str = "Cash withdrawal"):
    """Withdraw cash from available balance"""
    if amount <= 0:
        raise ValueError("Amount must be positive")

    balance = get_user_balance(db, user_id)
    if not balance or balance.available_balance < amount:
        raise ValueError("Insufficient available balance")

    # Update balance
    balance.available_balance -= amount
    balance.total_balance = balance.available_balance - balance.loan_balance
    balance.last_updated = datetime.utcnow()

    # Create transaction record
    transaction = create_loan_transaction(
        db, user_id, amount, "withdrawal", description
    )

    db.commit()
    db.refresh(balance)

    return transaction, balance


# Add to crud.py

def process_ticket_payment(db: Session, user_id: int, amount: float, ticket_id: int, description: str = ""):
    """
    Process ticket payment with automatic deduction from balance
    Returns: (success: bool, used_loan: bool, message: str)
    """
    balance = get_user_balance(db, user_id)

    if not balance:
        balance = create_user_balance(db, user_id)

    # Try to use available balance first
    if balance.available_balance >= amount:
        # Sufficient balance - deduct from available balance
        update_user_balance(db, user_id, amount, "withdraw")
        create_loan_transaction(
            db, user_id, amount, "ticket_payment",
            f"Ticket payment: {description}"
        )
        return True, False, "Ticket paid from available balance"

    # Check if we can use loan for the remaining amount
    remaining_amount = amount - balance.available_balance
    if can_borrow_more(db, user_id, remaining_amount):
        # Use all available balance and borrow the rest
        if balance.available_balance > 0:
            update_user_balance(db, user_id, balance.available_balance, "withdraw")

        # Borrow the remaining amount
        update_user_balance(db, user_id, remaining_amount, "borrow")
        create_loan_transaction(
            db, user_id, remaining_amount, "borrow",
            f"Loan for ticket payment: {description}"
        )

        # Apply interest immediately
        apply_interest_to_loan(db, user_id)

        return True, True, f"Ticket paid. Used ${balance.available_balance} from balance and borrowed ${remaining_amount}"

    return False, False, "Insufficient balance and cannot borrow more (max $20 loan reached)"


def manual_ticket_payment(db: Session, ticket_id: int):
    """
    Manually process ticket payment (for cases where auto-deduction failed)
    """
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not ticket:
        return False, "Ticket not found"

    if ticket.is_paid:
        return False, "Ticket already paid"

    # Process payment
    success, used_loan, message = process_ticket_payment(
        db, ticket.user_id, ticket.amount,
        f"Manual payment for ticket #{ticket_id}"
    )

    if success:
        ticket.is_paid = True
        db.commit()
        return True, message
    else:
        return False, message


# Add to crud.py

def process_toll_payment(db: Session, user_id: int, amount: float, description: str = ""):
    """
    Process toll payment with automatic deduction from balance and loan fallback
    Returns: (success: bool, used_loan: bool, message: str)
    """
    balance = get_user_balance(db, user_id)

    if not balance:
        balance = create_user_balance(db, user_id)

    # Try to use available balance first
    if balance.available_balance >= amount:
        # Sufficient balance - deduct from available balance
        update_user_balance(db, user_id, amount, "withdraw")
        create_loan_transaction(
            db, user_id, amount, "toll_payment",
            f"Toll payment: {description}"
        )
        return True, False, "Toll paid from available balance"

    # Check if we can use loan for the remaining amount
    remaining_amount = amount - balance.available_balance
    if can_borrow_more(db, user_id, remaining_amount):
        # Use all available balance and borrow the rest
        if balance.available_balance > 0:
            update_user_balance(db, user_id, balance.available_balance, "withdraw")

        # Borrow the remaining amount
        update_user_balance(db, user_id, remaining_amount, "borrow")
        create_loan_transaction(
            db, user_id, remaining_amount, "borrow",
            f"Loan for toll payment: {description}"
        )

        # Apply interest immediately
        apply_interest_to_loan(db, user_id)

        return True, True, f"Toll paid. Used ${balance.available_balance} from balance and borrowed ${remaining_amount}"

    return False, False, "Insufficient balance and cannot borrow more (max $20 loan reached)"


def refund_toll_payment(db: Session, user_id: int, amount: float, used_loan: bool):
    """
    Refund a toll payment in case of transaction failure
    """
    try:
        if used_loan:
            # Reverse the loan transaction
            update_user_balance(db, user_id, amount, "repayment")
        else:
            # Refund the deducted balance
            update_user_balance(db, user_id, amount, "deposit")
        return True
    except Exception as e:
        # Log the error but don't raise, as we're already in an error state
        print(f"Error refunding payment: {e}")
        return False


# Add to crud.py

def auto_deduct_loan_on_deposit(db: Session, user_id: int, deposit_amount: float):
    """
    Automatically deduct outstanding loan amount from deposit
    Returns: (remaining_deposit: float, loan_paid: float, interest_paid: float)
    """
    balance = get_user_balance(db, user_id)

    if not balance or balance.loan_balance <= 0:
        return deposit_amount, 0.0, 0.0  # No loan to deduct

    # Calculate total owed (loan balance + any accrued interest)
    total_owed = balance.loan_balance

    # Check if deposit is enough to cover the loan
    if deposit_amount >= total_owed:
        # Pay off entire loan
        loan_paid = total_owed
        interest_paid = 0.0  # Interest is already included in loan_balance

        # Update balance - pay off loan
        balance.loan_balance = 0.0
        balance.total_balance = balance.available_balance  # Now total = available since loan is 0

        # Create repayment transaction
        create_loan_transaction(
            db, user_id, loan_paid, "auto_repayment",
            f"Auto loan repayment from deposit"
        )

        remaining_deposit = deposit_amount - loan_paid
        return remaining_deposit, loan_paid, interest_paid

    else:
        # Deposit only covers part of the loan
        loan_paid = deposit_amount
        interest_paid = 0.0

        # Update balance - reduce loan
        balance.loan_balance -= loan_paid
        balance.total_balance = balance.available_balance - balance.loan_balance

        # Create partial repayment transaction
        create_loan_transaction(
            db, user_id, loan_paid, "auto_repayment",
            f"Partial auto loan repayment from deposit"
        )

        remaining_deposit = 0.0
        return remaining_deposit, loan_paid, interest_paid


def load_cash_to_balance_with_auto_deduction(db: Session, user_id: int, amount: float,
                                             description: str = "Cash deposit"):
    """
    Load cash to user's balance with automatic loan deduction
    """
    if amount <= 0:
        raise ValueError("Amount must be positive")

    # Get or create balance record
    balance = get_user_balance(db, user_id)
    if not balance:
        balance = create_user_balance(db, user_id)

    # First, automatically deduct from any outstanding loan
    remaining_amount, loan_paid, interest_paid = auto_deduct_loan_on_deposit(db, user_id, amount)

    # Then add remaining amount to available balance
    if remaining_amount > 0:
        balance.available_balance += remaining_amount
        balance.total_balance = balance.available_balance - balance.loan_balance

        # Create deposit transaction for the remaining amount
        create_loan_transaction(
            db, user_id, remaining_amount, "deposit",
            f"{description} (after loan deduction)"
        )

    balance.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(balance)

    # Create a summary transaction for the entire process
    summary_transaction = create_loan_transaction(
        db, user_id, amount, "deposit_processed",
        f"Deposit processed: ${amount} loaded, ${loan_paid} auto-deducted for loan"
    )

    return summary_transaction, balance, loan_paid, interest_paid


# Add to crud.py

def process_parking_payment(db: Session, user_id: int, amount: float, description: str = ""):
    """
    Process parking payment with automatic deduction from balance and loan fallback
    Returns: (success: bool, used_loan: bool, message: str)
    """
    balance = get_user_balance(db, user_id)

    if not balance:
        balance = create_user_balance(db, user_id)

    # Try to use available balance first
    if balance.available_balance >= amount:
        # Sufficient balance - deduct from available balance
        update_user_balance(db, user_id, amount, "withdraw")
        create_loan_transaction(
            db, user_id, amount, "parking_payment",
            f"Parking payment: {description}"
        )
        return True, False, "Parking paid from available balance"

    # Check if we can use loan for the remaining amount
    remaining_amount = amount - balance.available_balance
    if can_borrow_more(db, user_id, remaining_amount):
        # Use all available balance and borrow the rest
        if balance.available_balance > 0:
            update_user_balance(db, user_id, balance.available_balance, "withdraw")

        # Borrow the remaining amount
        update_user_balance(db, user_id, remaining_amount, "borrow")
        create_loan_transaction(
            db, user_id, remaining_amount, "borrow",
            f"Loan for parking payment: {description}"
        )

        # Apply interest immediately
        apply_interest_to_loan(db, user_id)

        return True, True, f"Parking paid. Used ${balance.available_balance} from balance and borrowed ${remaining_amount}"

    return False, False, "Insufficient balance and cannot borrow more (max $20 loan reached)"


def check_parking_affordability(db: Session, user_id: int, amount: float):
    """
    Check if user can afford parking (considering loan availability)
    Returns: (can_afford: bool, message: str)
    """
    balance = get_user_balance(db, user_id)

    if not balance:
        balance = create_user_balance(db, user_id)

    # Check available balance + remaining loan capacity
    available_funds = balance.available_balance + (20.0 - balance.loan_balance)

    if available_funds >= amount:
        return True, f"Sufficient funds available (${available_funds})"
    else:
        return False, f"Insufficient funds. Need ${amount}, available ${available_funds}"


def update_email_preferences(db: Session, user_id: int, email_notifications: bool) -> models.User:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.email_notifications = email_notifications
        db.commit()
        db.refresh(user)
    return user


def get_vehicle_by_vin(db: Session, vin: str):
    return db.query(models.Vehicle).filter(models.Vehicle.vin == vin).first()


def get_vehicle_by_plate(db: Session, plate_number: str):
    return db.query(models.Vehicle).filter(models.Vehicle.plate_number == plate_number).first()


def create_vehicle_condition(db: Session, condition: schemas.VehicleConditionCreate):
    db_condition = models.VehicleCondition(**condition.dict())
    db.add(db_condition)
    db.commit()
    db.refresh(db_condition)
    return db_condition


def get_vehicle_conditions(db: Session, vehicle_id: int):
    return db.query(models.VehicleCondition).filter(
        models.VehicleCondition.vehicle_id == vehicle_id
    ).all()


# In crud.py, add these functions

def update_borrowed_usage(db: Session, user_id: int, amount: float):
    """Update how much of the borrowed money has been used"""
    balance = get_user_balance(db, user_id)
    if not balance:
        balance = create_user_balance(db, user_id)

    balance.used_borrowed_amount += amount
    balance.loan_balance = max(0, balance.borrowed_amount - balance.used_borrowed_amount)
    balance.total_balance = balance.available_balance - balance.loan_balance
    balance.last_updated = datetime.utcnow()

    db.commit()
    db.refresh(balance)
    return balance


def load_cash_to_balance_with_auto_deduction(db: Session, user_id: int, amount: float,
                                             description: str = "Cash deposit"):
    """Load cash and automatically deduct from outstanding loan"""
    balance = get_user_balance(db, user_id)
    if not balance:
        balance = create_user_balance(db, user_id)

    # Calculate how much is needed to pay off the used borrowed amount + interest
    total_owed = balance.used_borrowed_amount * 1.25  # 25% interest

    if total_owed > 0:
        # First, pay off the loan with the new cash
        loan_payment = min(amount, total_owed)
        interest_paid = loan_payment - (loan_payment / 1.25)  # Calculate interest portion

        # Reduce the used borrowed amount (principal repayment)
        principal_repaid = loan_payment - interest_paid
        balance.used_borrowed_amount = max(0, balance.used_borrowed_amount - principal_repaid)

        # The remaining amount goes to available balance
        remaining_amount = amount - loan_payment
        balance.available_balance += remaining_amount
    else:
        # No loan to pay, all goes to available balance
        loan_payment = 0
        interest_paid = 0
        balance.available_balance += amount

    # Recalculate loan balance and total balance
    balance.loan_balance = max(0, balance.borrowed_amount - balance.used_borrowed_amount) * 1.25
    balance.total_balance = balance.available_balance - balance.loan_balance
    balance.last_updated = datetime.utcnow()

    # Create transaction record
    transaction = create_loan_transaction(
        db, user_id, amount, "deposit", description
    )

    db.commit()
    db.refresh(balance)

    return transaction, balance, loan_payment, interest_paid


def can_borrow_more(db: Session, user_id: int, amount: float):
    """Check if user can borrow more money"""
    balance = get_user_balance(db, user_id)
    if not balance:
        return amount <= 20.0

    total_borrowed_after = balance.borrowed_amount + amount
    return total_borrowed_after <= 20.0


def update_user_balance(db: Session, user_id: int, amount: float, transaction_type: str):
    """Update user balance for borrow/repayment transactions"""
    balance = get_user_balance(db, user_id)
    if not balance:
        balance = create_user_balance(db, user_id)

    if transaction_type == "borrow":
        balance.borrowed_amount += amount
        # When borrowing, the full amount becomes available
        balance.available_balance += amount
    elif transaction_type == "repayment":
        # For repayment, we need to handle this differently now
        # since we track usage separately
        pass  # We'll handle repayment in the endpoint

    balance.total_balance = balance.available_balance - balance.loan_balance
    balance.last_updated = datetime.utcnow()

    db.commit()
    db.refresh(balance)
    return balance


def generate_police_docket_number(db: Session):
    """Generate a unique police docket number"""
    from datetime import datetime
    year = datetime.now().year
    # Format: YEAR-RANDOM6DIGITS
    import random
    while True:
        random_digits = random.randint(100000, 999999)
        docket_number = f"{year}-{random_digits}"
        # Check if unique
        existing = db.query(models.AccidentUser).filter(
            models.AccidentUser.police_docket_number == docket_number
        ).first()
        if not existing:
            return docket_number


def create_accident_report(db: Session, accident_data: schemas_accident.AccidentCreate, reported_by_id: int):
    """Create a new accident report"""
    try:
        # Generate police docket number
        docket_number = generate_police_docket_number(db)

        # Create accident record
        db_accident = models.AccidentUser(
            description=accident_data.description,
            location=accident_data.location,
            severity=accident_data.severity,
            police_docket_number=docket_number,
            reported_by_id=reported_by_id,
            status="reported"
        )

        db.add(db_accident)
        db.flush()  # Flush to get the accident ID without committing

        # Process vehicles involved
        at_fault_user_id = None
        for vehicle_data in accident_data.vehicles:
            # Find the vehicle and its owner
            vehicle = get_vehicle(db, vehicle_data.license_plate)
            user_id = vehicle.user_id if vehicle else None

            db_vehicle = models.AccidentVehicle(
                accident_id=db_accident.id,
                vehicle_id=vehicle.id if vehicle else None,
                user_id=user_id,
                license_plate=vehicle_data.license_plate,
                is_at_fault=vehicle_data.is_at_fault
            )

            if vehicle_data.is_at_fault:
                at_fault_user_id = user_id

            db.add(db_vehicle)

        # Set at-fault user
        db_accident.at_fault_user_id = at_fault_user_id

        # Add images
        for image_data in accident_data.images:
            db_image = models.AccidentImage(
                accident_id=db_accident.id,
                image_url=image_data.image_url,
                description=image_data.description
            )
            db.add(db_image)

        db.commit()
        db.refresh(db_accident)

        return db_accident

    except Exception as e:
        db.rollback()
        raise e


def get_accident_by_docket(db: Session, docket_number: str):
    """Get accident by police docket number"""
    return db.query(models.AccidentUser).filter(
        models.AccidentUser.police_docket_number == docket_number
    ).first()


def get_user_accidents(db: Session, user_id: int):
    """Get all accidents involving a user's vehicles"""
    return db.query(models.AccidentUser).join(models.AccidentVehicle).filter(
        models.AccidentVehicle.user_id == user_id
    ).all()


def create_accident_confirmation(db: Session, accident_id: int, user_id: int,
                                 confirmation_data: schemas_accident.AccidentConfirmationCreate):
    """Create accident confirmation from involved party"""
    # Check if user has a vehicle in this accident
    accident_vehicle = db.query(models.AccidentVehicle).filter(
        models.AccidentVehicle.accident_id == accident_id,
        models.AccidentVehicle.user_id == user_id
    ).first()

    if not accident_vehicle:
        raise ValueError("User not involved in this accident")

    # Create confirmation
    db_confirmation = models.AccidentConfirmation(
        accident_id=accident_id,
        user_id=user_id,
        vehicle_id=accident_vehicle.vehicle_id,
        confirmed=confirmation_data.confirmed,
        confirmation_timestamp=datetime.utcnow() if confirmation_data.confirmed else None,
        dispute_reason=confirmation_data.dispute_reason
    )

    db.add(db_confirmation)
    db.flush()

    # Check if all parties have confirmed
    update_accident_status(db, accident_id)

    db.commit()
    db.refresh(db_confirmation)
    return db_confirmation


def update_accident_status(db: Session, accident_id: int):
    """Update accident status based on confirmations"""
    accident = db.query(models.AccidentUser).filter(models.AccidentUser.id == accident_id).first()
    if not accident:
        return

    # Get all vehicles involved
    vehicles = db.query(models.AccidentVehicle).filter(
        models.AccidentVehicle.accident_id == accident_id
    ).all()

    # Get all confirmations
    confirmations = db.query(models.AccidentConfirmation).filter(
        models.AccidentConfirmation.accident_id == accident_id
    ).all()

    # If all involved parties have confirmed and agreed
    if len(confirmations) == len(vehicles):
        all_agreed = all(conf.confirmed for conf in confirmations)
        if all_agreed:
            accident.status = "confirmed"
        else:
            accident.status = "disputed"

    db.commit()
