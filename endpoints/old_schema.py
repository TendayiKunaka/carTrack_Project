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


class UserCreate(UserBase):
    password: constr(min_length=PASSWORD_MIN_LENGTH)


class User(UserBase):
    id: int
    balance: float = Field(ge=0)
    is_active: bool

    #     created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True


class VehicleBase(BaseModel):
    plate_number: constr(max_length=PLATE_LENGTH)
    make: constr(max_length=50)
    model: constr(max_length=50)
    year: int = Field(..., gt=1900, lt=2100)
    color: constr(max_length=30)
    mileage_at_import: int = Field(..., ge=0)


class VehicleCreate(VehicleBase):
    user_id: int
    road_worthiness_expiry: date


class Vehicle(VehicleBase):
    id: int
    user_id: int
    road_worthiness_expiry: date

    class Config:
        orm_mode = True


class TicketBase(BaseModel):
    violation_type: constr(max_length=100)
    amount: float = Field(..., gt=0)
    location: constr(max_length=LOCATION_LENGTH)
    plate_number: str


class TicketCreate(TicketBase):
    vehicle_plate: constr(max_length=PLATE_LENGTH)
    photo_url: Optional[constr(max_length=255)] = None


class TicketDispute(BaseModel):
    reason: str


class Ticket(TicketBase):
    id: int
    issue_date: datetime
    due_date: datetime
    is_paid: bool
    is_disputed: bool
    # dispute_resolved: bool
    photo_url: Optional[str]
    user_id: int
    vehicle_id: int
    officer_id: int

    class Config:
        orm_mode = True


class ViolationType(str, Enum):
    PARKING_EXPIRED = "parking_expired"
    NO_PARKING_ZONE = "no_parking_zone"
    HANDICAP_ZONE = "handicap_zone"
    FIRE_HYDRANT = "fire_hydrant"
    OTHER = "other"


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


class Ticket(TicketBase):
    id: int
    issue_date: datetime
    due_date: datetime
    is_paid: bool
    is_disputed: bool
    dispute_resolved: bool
    photo_url: Optional[str]
    officer_id: int
    user_id: int
    vehicle_id: int

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


class TicketStats(BaseModel):
    total_tickets: int
    paid_tickets: int
    unpaid_tickets: int
    disputed_tickets: int
    total_revenue: float
    by_violation_type: dict


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


class ParkingSession(ParkingSessionBase):
    id: int
    start_time: datetime
    end_time: Optional[datetime]
    amount: float
    is_paid: bool
    user_id: int
    vehicle_id: int

    class Config:
        orm_mode = True


class TollGateBase(BaseModel):
    name: constr(max_length=100)
    location: constr(max_length=LOCATION_LENGTH)
    amount: float = Field(..., gt=0)


class TollGateCreate(TollGateBase):
    pass


class TollGate(TollGateBase):
    id: int

    class Config:
        orm_mode = True


class TollTransactionBase(BaseModel):
    toll_gate_id: int
    vehicle_plate: constr(max_length=PLATE_LENGTH)


class TollTransactionCreate(TollTransactionBase):
    pass


class TollTransaction(TollTransactionBase):
    id: int
    timestamp: datetime
    amount: float
    user_id: int
    vehicle_id: int

    class Config:
        orm_mode = True


class AccidentBase(BaseModel):
    date: date
    description: constr(max_length=DESCRIPTION_LENGTH)
    severity: constr(max_length=50)
    vehicle_plate: constr(max_length=PLATE_LENGTH)


class AccidentCreate(AccidentBase):
    pass


class Accident(AccidentBase):
    id: int
    vehicle_id: int

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
    accidents: List[Accident]
    ownership_history: List[OwnershipHistory]
    tickets: List[Ticket]
    toll_transactions: List[TollTransaction]
    parking_sessions: List[ParkingSession]

    class Config:
        orm_mode = True
