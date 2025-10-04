from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


class AccidentImageCreate(BaseModel):
    image_url: str
    description: Optional[str] = None


class AccidentVehicleCreate(BaseModel):
    license_plate: str
    is_at_fault: bool = False


class AccidentCreate(BaseModel):
    description: str
    location: str
    severity: str
    vehicles: List[AccidentVehicleCreate]
    images: List[AccidentImageCreate]
    at_fault_plate: str  # License plate of the at-fault vehicle


class AccidentConfirmationCreate(BaseModel):
    confirmed: bool
    dispute_reason: Optional[str] = None


class AccidentImage(BaseModel):
    id: int
    image_url: str
    description: Optional[str] = None
    upload_timestamp: datetime

    class Config:
        from_attributes = True


class AccidentVehicle(BaseModel):
    id: int
    license_plate: str
    is_at_fault: bool
    vehicle_id: Optional[int]
    user_id: Optional[int]

    class Config:
        from_attributes = True


class AccidentConfirmation(BaseModel):
    id: int
    user_id: int
    vehicle_id: int
    confirmed: bool
    confirmation_timestamp: Optional[datetime]
    dispute_reason: Optional[str]

    class Config:
        from_attributes = True


class AccidentUser(BaseModel):
    id: int
    description: str
    location: str
    date_time: datetime
    severity: str
    police_docket_number: Optional[str]
    status: str
    reported_by_id: int
    at_fault_user_id: Optional[int]

    # Include relationships
    vehicles: List[AccidentVehicle]
    images: List[AccidentImage]
    confirmations: List[AccidentConfirmation]

    class Config:
        from_attributes = True
