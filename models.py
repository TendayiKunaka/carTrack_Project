from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    phone_number = Column(String)
    balance = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    email_notifications = Column(Boolean, default=True)

    vehicles = relationship("Vehicle", back_populates="owner")
    tickets = relationship("Ticket", back_populates="user")
    toll_transactions = relationship("TollTransaction", back_populates="user")
    parking_sessions = relationship("ParkingSession", back_populates="user")
    loan_transactions = relationship("LoanTransaction", back_populates="user")
    email_notifications = Column(Boolean, default=True)
    balance = relationship("UserBalance", back_populates="user", uselist=False, lazy='joined')


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    # User-provided fields
    plate_number = Column(String(20), unique=True, index=True)
    make = Column(String(50))
    model = Column(String(50))
    year = Column(Integer)
    color = Column(String(30))
    mileage_at_import = Column(Integer)
    road_worthiness_expiry = Column(DateTime)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Registry-only fields (can be null initially)
    vin = Column(String(17), unique=True, nullable=True)
    engine_number = Column(String(50), nullable=True)
    chassis_number = Column(String(50), nullable=True)
    engine_capacity_cc = Column(Integer, nullable=True)
    country_of_export = Column(String(50), nullable=True)

    # Relationships
    owner = relationship("User", back_populates="vehicles")
    tickets = relationship("Ticket", back_populates="vehicle")
    toll_transactions = relationship("TollTransaction", back_populates="vehicle")
    parking_sessions = relationship("ParkingSession", back_populates="vehicle")
    accidents = relationship("Accident", back_populates="vehicle")
    ownership_history = relationship("OwnershipHistory", back_populates="vehicle")
    conditions = relationship("VehicleCondition", back_populates="vehicle")


class VehicleCondition(Base):
    __tablename__ = "vehicle_conditions"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    inspection_date = Column(DateTime(timezone=True), default=datetime.utcnow)
    odometer_reading = Column(Integer)
    paint_condition = Column(Text)
    body_panel_condition = Column(Text)
    tire_condition = Column(Text)
    glass_condition = Column(Text)
    headlights_condition = Column(Text)
    interior_condition = Column(Text)
    dashboard_condition = Column(Text)
    upholstery_condition = Column(Text)
    electronics_status = Column(Text)
    roadworthiness_certificate_date = Column(Date)

    vehicle = relationship("Vehicle", back_populates="conditions")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    violation_type = Column(String)
    amount = Column(Float)
    issue_date = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime)
    is_paid = Column(Boolean, default=False)
    is_disputed = Column(Boolean, default=False)
    dispute_resolved = Column(Boolean, default=False)
    photo_url = Column(String, nullable=True)
    location = Column(String)
    notes = Column(String, nullable=True)
    parking_worker_id = Column(Integer, ForeignKey("parking_workers.id"), nullable=True)
    police_officer_id = Column(Integer, ForeignKey("police.id"), nullable=True)  # Add this
    user_id = Column(Integer, ForeignKey("users.id"))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))

    # Relationships
    user = relationship("User", back_populates="tickets")
    vehicle = relationship("Vehicle", back_populates="tickets")
    parking_worker = relationship("ParkingWorker", back_populates="issued_tickets")
    police_officer = relationship("Police", back_populates="issued_tickets")  # Keep this
    # In models.py, add to Ticket model
    payment_method = Column(String, default="balance")  # balance, cash, card, etc.


class Police(Base):
    __tablename__ = "police"

    id = Column(Integer, primary_key=True, index=True)
    badge_number = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    station = Column(String)
    is_active = Column(Boolean, default=True)

    # Change this relationship name to match Ticket model
    issued_tickets = relationship("Ticket", back_populates="police_officer")  # Changed from "officer"


class ParkingWorker(Base):
    __tablename__ = "parking_workers"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    zone = Column(String)
    is_active = Column(Boolean, default=True)

    # Add relationship to tickets
    issued_tickets = relationship("Ticket", back_populates="parking_worker")


class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    zone = Column(String)
    vehicle_plate = Column(String)  # Make sure this exists
    amount = Column(Float, default=0.0)  # Make sure this exists
    is_paid = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))

    user = relationship("User", back_populates="parking_sessions")
    vehicle = relationship("Vehicle", back_populates="parking_sessions")


class TollRoute(Base):
    __tablename__ = "toll_routes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    description = Column(String)

    # Relationships
    toll_gates = relationship("TollGateRoute", back_populates="route")
    transactions = relationship("TollTransaction", back_populates="route")

    # Add this property to calculate total amount
    @property
    def total_amount(self):
        if not self.toll_gates:
            return 0.0
        return sum(tg.toll_gate.amount for tg in self.toll_gates)


class TollGateRoute(Base):
    __tablename__ = "toll_gate_routes"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("toll_routes.id"))
    toll_gate_id = Column(Integer, ForeignKey("toll_gates.id"))
    order = Column(Integer)  # Sequence order on the route

    # Relationships
    route = relationship("TollRoute", back_populates="toll_gates")
    toll_gate = relationship("TollGate")


class TollGate(Base):
    __tablename__ = "toll_gates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    location = Column(String)
    amount = Column(Float)

    # Relationships
    routes = relationship("TollGateRoute", back_populates="toll_gate")
    transactions = relationship("TollTransaction", back_populates="toll_gate")


class TollTransaction(Base):
    __tablename__ = "toll_transactions"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    payment_method = Column(String)  # "cash", "balance", "keypass"
    status = Column(String, default="completed")  # "pending", "completed", "failed"

    # Foreign keys
    toll_gate_id = Column(Integer, ForeignKey("toll_gates.id"))
    route_id = Column(Integer, ForeignKey("toll_routes.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    keypass_id = Column(Integer, ForeignKey("toll_keypasses.id"), nullable=True)

    # Relationships
    toll_gate = relationship("TollGate", back_populates="transactions")
    route = relationship("TollRoute", back_populates="transactions")
    user = relationship("User")
    vehicle = relationship("Vehicle")
    keypass = relationship("TollKeypass", back_populates="transactions")


class TollKeypass(Base):
    __tablename__ = "toll_keypasses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    amount = Column(Float)
    balance = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)

    # Relationships
    user = relationship("User")
    vehicle = relationship("Vehicle")
    transactions = relationship("TollTransaction", back_populates="keypass")


class Accident(Base):
    __tablename__ = "accidents"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)
    location = Column(String)
    date_time = Column(DateTime, default=datetime.utcnow)
    severity = Column(String)
    photo_url = Column(String, nullable=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    reported_by_id = Column(Integer, ForeignKey("registry_workers.id"), nullable=False)
    vehicle_plate = Column(String, nullable=False)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="accidents")
    reported_by = relationship("RegistryWorker", back_populates="reported_accidents")

    def __init__(self, **kwargs):
        # Auto-populate vehicle_plate from vehicle if not provided
        if 'vehicle_plate' not in kwargs or kwargs['vehicle_plate'] is None:
            if 'vehicle_id' in kwargs:
                # You might need to handle this differently depending on your setup
                pass
        super().__init__(**kwargs)


class AccidentUser(Base):
    __tablename__ = "accidentuser"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text)
    location = Column(String)
    date_time = Column(DateTime, default=datetime.utcnow)
    severity = Column(String)
    police_docket_number = Column(String, unique=True, nullable=True)
    status = Column(String, default="reported")
    reported_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    at_fault_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships - FIXED back_populates references
    reported_by = relationship("User", foreign_keys=[reported_by_id])
    at_fault_user = relationship("User", foreign_keys=[at_fault_user_id])
    vehicles = relationship("AccidentVehicle", back_populates="accident")
    images = relationship("AccidentImage", back_populates="accident")
    confirmations = relationship("AccidentConfirmation", back_populates="accident")


class AccidentVehicle(Base):
    __tablename__ = "accident_vehicles"

    id = Column(Integer, primary_key=True, index=True)
    accident_id = Column(Integer, ForeignKey("accidentuser.id"))  # Fixed foreign key
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    license_plate = Column(String)
    is_at_fault = Column(Boolean, default=False)

    # Relationships - FIXED back_populates
    accident = relationship("AccidentUser", back_populates="vehicles")
    vehicle = relationship("Vehicle")
    user = relationship("User")


class AccidentImage(Base):
    __tablename__ = "accident_images"

    id = Column(Integer, primary_key=True, index=True)
    accident_id = Column(Integer, ForeignKey("accidentuser.id"))  # Fixed foreign key
    image_url = Column(String)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    description = Column(String, nullable=True)

    # Relationships - FIXED back_populates
    accident = relationship("AccidentUser", back_populates="images")


class AccidentConfirmation(Base):
    __tablename__ = "accident_confirmations"

    id = Column(Integer, primary_key=True, index=True)
    accident_id = Column(Integer, ForeignKey("accidentuser.id"))  # Fixed foreign key
    user_id = Column(Integer, ForeignKey("users.id"))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    confirmed = Column(Boolean, default=False)
    confirmation_timestamp = Column(DateTime, nullable=True)
    dispute_reason = Column(Text, nullable=True)

    # Relationships - FIXED back_populates
    accident = relationship("AccidentUser", back_populates="confirmations")
    user = relationship("User")
    vehicle = relationship("Vehicle")


class RegistryWorker(Base):
    __tablename__ = "registry_workers"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)

    # Add relationship to accidents
    reported_accidents = relationship("Accident", back_populates="reported_by")


class OwnershipHistory(Base):
    __tablename__ = "ownership_history"

    id = Column(Integer, primary_key=True, index=True)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    user_id = Column(Integer, ForeignKey("users.id"))

    vehicle = relationship("Vehicle", back_populates="ownership_history")
    user = relationship("User")

    # Add this property
    @property
    def vehicle_plate(self):
        return self.vehicle.plate_number if self.vehicle else None


class LoanTransaction(Base):
    __tablename__ = "loan_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, default=0.0)
    transaction_type = Column(String)  # 'borrow', 'repayment', 'interest'
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    interest_applied = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="loan_transactions")


class UserBalance(Base):
    __tablename__ = "user_balances"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    available_balance = Column(Float, default=0.0)
    loan_balance = Column(Float, default=0.0)
    total_balance = Column(Float, default=0.0)  # available_balance - loan_balance
    borrowed_amount = Column(Float, default=0.0)  # Total amount borrowed
    used_borrowed_amount = Column(Float, default=0.0)  # Amount actually used from borrowed money
    last_updated = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="balance")
