from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, constr
from datetime import datetime, date
from enum import Enum

# Common field constraints
USERNAME_LENGTH = 50
EMAIL_LENGTH = 100
NAME_LENGTH = 100
PHONE_LENGTH = 20
PASSWORD_MIN_LENGTH = 8
PLATE_LENGTH = 20
ZONE_LENGTH = 50
LOCATION_LENGTH = 255
DESCRIPTION_LENGTH = 500


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class UserBase(BaseModel):
    username: constr(max_length=USERNAME_LENGTH)
    email: EmailStr
    full_name: constr(max_length=NAME_LENGTH)
    phone_number: constr(max_length=PHONE_LENGTH)
    email_notifications: bool = True
    address: constr(max_length=NAME_LENGTH)
    town: constr(max_length=NAME_LENGTH)
    city: constr(max_length=NAME_LENGTH)


class UserCreate(UserBase):
    password: constr(min_length=PASSWORD_MIN_LENGTH)


class User(UserBase):
    id: int
    balance: Optional[float] = Field(ge=0, default=None)
    is_active: bool

    class Config:
        orm_mode = True


class EmailPreferences(BaseModel):
    email_notifications: bool


# User-facing schema (limited fields)
class VehicleCreate(BaseModel):
    plate_number: constr(max_length=20)
    make: constr(max_length=50)
    model: constr(max_length=50)
    year: int
    color: constr(max_length=30)
    mileage_at_import: Optional[int] = None
    road_worthiness_expiry: Optional[datetime] = None


# Registry-facing schema (all fields)
class VehicleRegistryUpdate(BaseModel):
    vin: Optional[constr(max_length=17)] = None
    engine_number: Optional[constr(max_length=50)] = None
    chassis_number: Optional[constr(max_length=50)] = None
    engine_capacity_cc: Optional[int] = None
    country_of_export: Optional[constr(max_length=50)] = None


# Full vehicle schema for responses
class Vehicle(BaseModel):
    id: int
    plate_number: str
    make: str
    model: str
    year: int
    color: str
    mileage_at_import: Optional[int] = None
    road_worthiness_expiry: Optional[datetime] = None
    user_id: Optional[int] = None

    # Registry fields (optional in response)
    vin: Optional[str] = None
    engine_number: Optional[str] = None
    chassis_number: Optional[str] = None
    engine_capacity_cc: Optional[int] = None
    country_of_export: Optional[str] = None

    class Config:
        orm_mode = True


class VehicleConditionBase(BaseModel):
    vehicle_id: int
    inspection_date: Optional[datetime] = None
    odometer_reading: Optional[int] = None
    paint_condition: Optional[str] = None
    body_panel_condition: Optional[str] = None
    tire_condition: Optional[str] = None
    glass_condition: Optional[str] = None
    headlights_condition: Optional[str] = None
    interior_condition: Optional[str] = None
    dashboard_condition: Optional[str] = None
    upholstery_condition: Optional[str] = None
    electronics_status: Optional[str] = None
    roadworthiness_certificate_date: Optional[date] = None


class VehicleConditionCreate(VehicleConditionBase):
    pass


class VehicleCondition(VehicleConditionBase):
    id: int

    class Config:
        orm_mode = True


class VehicleRegistryCreate(BaseModel):
    plate_number: constr(max_length=20)
    make: constr(max_length=50)
    model: constr(max_length=50)
    year: int
    color: constr(max_length=30)
    vin: constr(max_length=17)
    engine_number: Optional[constr(max_length=50)] = None
    chassis_number: Optional[constr(max_length=50)] = None
    engine_capacity_cc: Optional[int] = None
    country_of_export: Optional[constr(max_length=50)] = None
    mileage_at_import: Optional[int] = None
    road_worthiness_expiry: Optional[datetime] = None


class ViolationType(str, Enum):
    PARKING_EXPIRED = "parking_expired"
    NO_PARKING_ZONE = "no_parking_zone"
    HANDICAP_ZONE = "handicap_zone"
    FIRE_HYDRANT = "fire_hydrant"
    OTHER = "other"


# KEEP ONLY ONE VERSION - DELETE ANY DUPLICATES!

class TicketBase(BaseModel):
    plate_number: str = Field(..., description="Vehicle plate number")
    violation_type: ViolationType
    amount: float = Field(..., gt=0, description="Fine amount")
    location: str
    notes: Optional[str] = None


class TicketCreate(TicketBase):
    pass


class TicketUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    is_paid: Optional[bool] = None
    is_disputed: Optional[bool] = None
    dispute_resolved: Optional[bool] = None


class TicketDispute(BaseModel):
    reason: str
    evidence_url: Optional[str] = None


'''class Ticket(BaseModel):
    id: int
    issue_date: datetime
    due_date: datetime
    is_paid: bool
    is_disputed: bool
    dispute_resolved: bool
    photo_url: Optional[str]
    parking_worker_id: int  # Make sure this matches
    # Add this if you keep the police relationship:
    police_officer_id: Optional[int] = None  # Make it optional
    user_id: int
    vehicle_id: int

    class Config:
        orm_mode = True'''


# In schemas.py, update the Ticket schema

class Ticket(BaseModel):
    id: int
    issue_date: datetime
    due_date: datetime
    is_paid: bool
    is_disputed: bool
    dispute_resolved: bool
    photo_url: Optional[str]
    parking_worker_id: int
    police_officer_id: Optional[int] = None
    user_id: int
    vehicle_id: int
    payment_message: Optional[str] = None  # Add this field
    used_loan: Optional[bool] = None  # Add this field

    class Config:
        orm_mode = True


class TicketStats(BaseModel):
    total_tickets: int
    paid_tickets: int
    unpaid_tickets: int
    disputed_tickets: int
    total_revenue: float
    by_violation_type: dict


class BulkTicketCreate(BaseModel):
    tickets: List[TicketCreate]


class DisputeCreate(BaseModel):
    reason: str


class Dispute(BaseModel):
    dispute_id: int
    ticket_id: int
    user_id: int
    dispute_date: datetime
    reason: str
    status: str
    resolution_date: Optional[datetime] = None
    resolved_by: Optional[int] = None
    resolution_notes: Optional[str] = None

    class Config:
        from_attributes = True


class PoliceBase(BaseModel):
    badge_number: constr(max_length=50)
    username: constr(max_length=USERNAME_LENGTH)
    full_name: constr(max_length=NAME_LENGTH)
    station: constr(max_length=100)


class PoliceCreate(PoliceBase):
    password: constr(min_length=PASSWORD_MIN_LENGTH)


class Police(PoliceBase):
    id: int
    is_active: bool

    class Config:
        orm_mode = True


class ParkingWorkerBase(BaseModel):
    employee_id: constr(max_length=50)
    username: constr(max_length=USERNAME_LENGTH)
    full_name: constr(max_length=NAME_LENGTH)
    zone: constr(max_length=ZONE_LENGTH)


class ParkingWorkerCreate(ParkingWorkerBase):
    password: constr(min_length=PASSWORD_MIN_LENGTH)


class ParkingWorker(ParkingWorkerBase):
    id: int
    is_active: bool

    class Config:
        orm_mode = True


class RegistryWorkerBase(BaseModel):
    employee_id: constr(max_length=50)
    username: constr(max_length=USERNAME_LENGTH)
    full_name: constr(max_length=NAME_LENGTH)


class RegistryWorkerCreate(RegistryWorkerBase):
    password: constr(min_length=PASSWORD_MIN_LENGTH)


class RegistryWorker(RegistryWorkerBase):
    id: int
    is_active: bool

    class Config:
        orm_mode = True


class ParkingSessionBase(BaseModel):
    zone: constr(max_length=ZONE_LENGTH)
    vehicle_plate: constr(max_length=PLATE_LENGTH)


class ParkingSessionCreate(ParkingSessionBase):
    pass


# In schemas.py, update the ParkingSession schema

class ParkingSession(ParkingSessionBase):
    id: int
    start_time: datetime
    end_time: Optional[datetime]
    amount: float
    is_paid: bool
    user_id: int
    vehicle_id: int
    payment_message: Optional[str] = None  # Add this field
    used_loan: Optional[bool] = None  # Add this field

    class Config:
        orm_mode = True


class PaymentMethod(str, Enum):
    CASH = "cash"
    BALANCE = "balance"
    KEYPASS = "keypass"

class AccidentBase(BaseModel):
    description: constr(max_length=DESCRIPTION_LENGTH)
    location: constr(max_length=100)
    severity: constr(max_length=50)
    # Remove vehicle_plate from base since it's not in the ORM model


class AccidentCreate(AccidentBase):
    vehicle_plate: constr(max_length=PLATE_LENGTH)  # Keep only in create


class Accident(AccidentBase):
    id: int
    date_time: datetime
    photo_url: Optional[str] = None
    reported_by_id: int
    vehicle_plate: Optional[str] = None  # Make this optional

    class Config:
        orm_mode = True


class OwnershipHistoryBase(BaseModel):
    vehicle_plate: constr(max_length=PLATE_LENGTH)
    user_id: int
    start_date: date
    end_date: Optional[date]


class OwnershipHistoryCreate(OwnershipHistoryBase):
    pass


class OwnershipHistory(OwnershipHistoryBase):
    id: int
    vehicle_id: int

    class Config:
        orm_mode = True


class VehicleSearchResult(BaseModel):
    vehicle: Vehicle
    accidents: List[Accident] = []  # Make optional with default
    ownership_history: List[OwnershipHistory] = []  # Make optional with default
    tickets: List[Ticket] = []  # Make optional with default
    parking_sessions: List[ParkingSession] = []  # Make optional with default

    class Config:
        orm_mode = True


class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class TollGateBase(BaseModel):
    name: str
    location: str
    amount: float


class TollGateCreate(TollGateBase):
    pass


class TollGate(TollGateBase):
    id: int

    class Config:
        orm_mode = True


class TollRouteBase(BaseModel):
    name: str
    description: Optional[str] = None


class TollRouteCreate(TollRouteBase):
    toll_gate_ids: List[int] = Field(..., description="List of toll gate IDs in order")


class TollRoute(TollRouteBase):
    id: int
    total_amount: float

    class Config:
        orm_mode = True


class TollKeypassBase(BaseModel):
    amount: float = Field(..., gt=0, description="Initial amount for the keypass")
    vehicle_plate: Optional[str] = Field(None, description="Optional vehicle plate to associate with keypass")
    expires_in_days: int = Field(30, description="Number of days until keypass expires")


class TollKeypassCreate(TollKeypassBase):
    pass


class TollKeypass(TollKeypassBase):
    id: int
    code: str
    balance: float
    created_at: datetime
    expires_at: datetime
    is_active: bool
    user_id: int
    payment_message: Optional[str] = None  # Add this
    used_loan: Optional[bool] = None  # Add this

    class Config:
        orm_mode = True


class TollTransactionBase(BaseModel):
    vehicle_plate: str
    payment_method: PaymentMethod = PaymentMethod.BALANCE
    keypass_code: Optional[str] = Field(None, description="Required if payment_method is 'keypass'")


class TollTransactionCreate(TollTransactionBase):
    toll_gate_id: Optional[int] = Field(None, description="Either toll_gate_id or route_id must be provided")
    route_id: Optional[int] = Field(None, description="Either toll_gate_id or route_id must be provided")

    class Config:
        schema_extra = {
            "example": {
                "vehicle_plate": "ABC123",
                "toll_gate_id": 1,
                "payment_method": "balance",
                "keypass_code": None
            }
        }


class RoutePaymentCreate(BaseModel):
    vehicle_plate: str
    route_id: int
    payment_method: PaymentMethod = PaymentMethod.BALANCE
    keypass_code: Optional[str] = Field(None, description="Required if payment_method is 'keypass'")


class TollTransaction(TollTransactionBase):
    id: int
    amount: float
    timestamp: datetime
    status: TransactionStatus
    toll_gate_id: Optional[int]
    route_id: Optional[int]
    user_id: int
    vehicle_id: int
    keypass_id: Optional[int]

    # Additional details (could be added via properties or relationships)
    toll_gate_name: Optional[str] = None
    route_name: Optional[str] = None
    vehicle_plate: str

    class Config:
        orm_mode = True


class TollGateRouteBase(BaseModel):
    route_id: int
    toll_gate_id: int
    order: int


class TollGateRoute(TollGateRouteBase):
    id: int

    class Config:
        orm_mode = True


class TollPaymentResponse(BaseModel):
    transaction: TollTransaction
    new_balance: Optional[float] = None
    keypass_balance: Optional[float] = None
    payment_message: Optional[str] = None
    used_loan: Optional[bool] = None

    class Config:
        orm_mode = True


class KeypassPurchaseResponse(BaseModel):
    keypass: TollKeypass
    new_balance: float


# Statistics models
class TollTransactionStats(BaseModel):
    total_transactions: int
    total_revenue: float
    cash_transactions: int
    balance_transactions: int
    keypass_transactions: int


class UserTollStats(BaseModel):
    user_id: int
    total_spent: float
    total_transactions: int
    favorite_payment_method: str
    most_used_route: Optional[str] = None


# Filter models for querying transactions
class TollTransactionFilter(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    payment_method: Optional[PaymentMethod] = None
    vehicle_plate: Optional[str] = None
    toll_gate_id: Optional[int] = None
    route_id: Optional[int] = None


# Update models
class TollKeypassUpdate(BaseModel):
    is_active: Optional[bool] = None


class TollGateUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    amount: Optional[float] = None


# Simplified models for quick responses
class SimplifiedTollTransaction(BaseModel):
    id: int
    amount: float
    timestamp: datetime
    payment_method: str
    toll_gate_name: Optional[str]
    route_name: Optional[str]

    class Config:
        orm_mode = True


class SimplifiedTollKeypass(BaseModel):
    id: int
    code: str
    balance: float
    expires_at: datetime
    is_active: bool

    class Config:
        orm_mode = True


class VehicleSearchResult(BaseModel):
    vehicle: Vehicle
    accidents: List[Accident] = []
    ownership_history: List[OwnershipHistory] = []
    tickets: List[Ticket] = []
    parking_sessions: List[ParkingSession] = []
    conditions: List[VehicleCondition] = []

    class Config:
        orm_mode = True


# Add these new schemas

class LoanTransactionBase(BaseModel):
    amount: float = Field(..., gt=0)
    description: Optional[str] = None


class LoanTransactionCreate(LoanTransactionBase):
    pass


class LoanTransaction(LoanTransactionBase):
    id: int
    user_id: int
    transaction_type: str
    timestamp: datetime
    interest_applied: bool

    class Config:
        orm_mode = True


class UserBalanceBase(BaseModel):
    available_balance: float
    loan_balance: float
    total_balance: float


class UserBalance(UserBalanceBase):
    user_id: int
    last_updated: datetime

    class Config:
        orm_mode = True


class BorrowRequest(BaseModel):
    amount: float = Field(..., gt=0, le=20, description="Amount to borrow (max $20)")
    purpose: str = Field(..., description="Purpose of borrowing (toll, parking, etc.)")


class RepaymentRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount to repay")


# Add to PaymentMethod enum if not already there
class PaymentMethod(str, Enum):
    CASH = "cash"
    BALANCE = "balance"
    KEYPASS = "keypass"
    LOAN = "loan"  # Add this new payment method


class CustomerBalanceResponse(BaseModel):
    user_id: int
    username: str
    full_name: str
    email: str
    available_balance: float
    loan_balance: float
    total_balance: float
    last_updated: datetime
    can_borrow_more: bool
    remaining_borrow_limit: float

    class Config:
        orm_mode = True


class CustomerBalanceRequest(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None


class CustomerTransactionResponse(BaseModel):
    id: int
    user_id: int
    username: str
    full_name: str
    amount: float
    transaction_type: str
    description: str
    timestamp: datetime
    interest_applied: bool

    class Config:
        orm_mode = True


# Add to schemas.py

class CashLoadRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount to load (must be positive)")
    user_id: Optional[int] = Field(None, description="User ID to load cash for (admin only)")
    description: Optional[str] = Field("Cash deposit", description="Description of the deposit")


class CashLoadResponse(BaseModel):
    transaction: LoanTransaction
    new_balance: UserBalance
    loan_paid: float = 0.0
    interest_paid: float = 0.0
    message: str

    class Config:
        orm_mode = True


class LoanDeductionDetail(BaseModel):
    original_deposit: float
    loan_paid: float
    interest_paid: float
    remaining_balance: float
    new_available_balance: float
    new_loan_balance: float

    class Config:
        orm_mode = True


class CashTransferRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount to transfer")
    target_user_id: int = Field(..., description="User ID to transfer to")
    description: Optional[str] = Field("Balance transfer", description="Description of the transfer")


# In schemas.py
class UseBorrowedRequest(BaseModel):
    amount: float = Field(..., gt=0, le=20, description="Amount to use from borrowed funds")
    purpose: str = Field(..., description="Purpose of using borrowed funds")


class VehiclePlateRequest(BaseModel):
    plate_number: constr(max_length=20)


class VehicleTransferRequest(BaseModel):
    plate_number: constr(max_length=20)
    new_user_id: int
