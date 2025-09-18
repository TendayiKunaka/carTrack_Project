from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from datetime import datetime
import crud
import models
import schemas
from auth import get_current_user, get_db, get_current_registry_worker, pwd_context
# FastAPI and related imports
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional, List
import aiofiles
import os
import uuid
from datetime import datetime, timedelta
from fastapi import UploadFile, File

router = APIRouter(prefix="/registry", tags=["registry"])


# Add to crud.py:
def get_registry_worker_by_username(db: Session, username: str):
    return db.query(models.RegistryWorker).filter(models.RegistryWorker.username == username).first()


def create_registry_worker(db: Session, worker: schemas.RegistryWorkerCreate):
    db_worker = models.RegistryWorker(
        employee_id=worker.employee_id,
        username=worker.username,
        hashed_password=pwd_context.hash(worker.password),
        full_name=worker.full_name
    )
    db.add(db_worker)
    db.commit()
    db.refresh(db_worker)
    return db_worker


@router.post("/registry-workers/", response_model=schemas.RegistryWorker)
def create_registry_worker(worker: schemas.RegistryWorkerCreate, db: Session = Depends(get_db)):
    # Check if worker exists
    db_worker = crud.get_registry_worker_by_username(db, username=worker.username)
    if db_worker:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Create new worker
    db_worker = crud.create_registry_worker(db=db, worker=worker)
    if db_worker is None:
        raise HTTPException(status_code=400, detail="Registry worker already exists")
    return db_worker


@router.post("/accidents/", response_model=schemas.Accident)
def create_accident(
        accident: schemas.AccidentCreate,
        db: Session = Depends(get_db),
        current_user: models.RegistryWorker = Depends(get_current_registry_worker)
):
    # Verify the vehicle exists and get its plate if needed
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == accident.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # If vehicle_plate is not provided, use the vehicle's plate number
    if accident.vehicle_plate is None:
        accident.vehicle_plate = vehicle.plate_number

    db_accident = models.Accident(
        **accident.dict(),
        reported_by_id=current_user.id
    )

    try:
        db.add(db_accident)
        db.commit()
        db.refresh(db_accident)
        return db_accident
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating accident report: {str(e)}")


@router.post("/ownership/", response_model=schemas.OwnershipHistory)
def record_ownership_change(
        ownership: schemas.OwnershipHistoryCreate,
        current_user: models.RegistryWorker = Depends(get_current_registry_worker),
        db: Session = Depends(get_db)
):
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == ownership.vehicle_plate
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # End current ownership
    current_ownership = db.query(models.OwnershipHistory).filter(
        models.OwnershipHistory.vehicle_id == vehicle.id,
        models.OwnershipHistory.end_date == None
    ).first()

    if current_ownership:
        current_ownership.end_date = datetime.utcnow()
        db.commit()

    # Create new ownership
    db_ownership = models.OwnershipHistory(
        vehicle_id=vehicle.id,
        user_id=ownership.user_id,
        start_date=ownership.start_date or datetime.utcnow()
    )
    db.add(db_ownership)
    db.commit()
    db.refresh(db_ownership)

    # Convert to dictionary and add vehicle_plate
    ownership_dict = {
        "id": db_ownership.id,
        "vehicle_id": db_ownership.vehicle_id,
        "user_id": db_ownership.user_id,
        "start_date": db_ownership.start_date,
        "end_date": db_ownership.end_date,
        "vehicle_plate": ownership.vehicle_plate  # Use the plate from the request
    }

    return schemas.OwnershipHistory(**ownership_dict)


# In endpoints/registry.py
@router.post("/vehicles/", response_model=schemas.Vehicle)
def create_vehicle(
    vehicle: schemas.VehicleRegistryCreate,
    current_user: models.RegistryWorker = Depends(get_current_registry_worker),
    db: Session = Depends(get_db)
):
    """
    Create a new vehicle (registry worker only) - with full technical details
    """
    # Check if plate already exists
    existing_vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == vehicle.plate_number
    ).first()
    if existing_vehicle:
        raise HTTPException(
            status_code=400,
            detail="Vehicle with this plate number already exists"
        )

    # Check if VIN already exists
    if vehicle.vin:
        existing_vin = db.query(models.Vehicle).filter(
            models.Vehicle.vin == vehicle.vin
        ).first()
        if existing_vin:
            raise HTTPException(
                status_code=400,
                detail="Vehicle with this VIN already exists"
            )

    # Create the vehicle - EXPLICITLY set user_id to None
    db_vehicle = models.Vehicle(
        plate_number=vehicle.plate_number,
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        color=vehicle.color,
        vin=vehicle.vin,
        engine_number=vehicle.engine_number,
        chassis_number=vehicle.chassis_number,
        engine_capacity_cc=vehicle.engine_capacity_cc,
        country_of_export=vehicle.country_of_export,
        mileage_at_import=vehicle.mileage_at_import,
        road_worthiness_expiry=vehicle.road_worthiness_expiry,
        user_id=None  # Explicitly set to None
    )

    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


@router.post("/vehicle-conditions/", response_model=schemas.VehicleCondition)
def create_vehicle_condition(
        condition: schemas.VehicleConditionCreate,
        current_user: models.RegistryWorker = Depends(get_current_registry_worker),
        db: Session = Depends(get_db)
):
    # Verify vehicle exists
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == condition.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return crud.create_vehicle_condition(db=db, condition=condition)


@router.get("/vehicles/{vehicle_id}/conditions1", response_model=List[schemas.VehicleCondition])
def get_vehicle_conditions1(
        vehicle_id: int,
        current_user: models.RegistryWorker = Depends(get_current_registry_worker),
        db: Session = Depends(get_db)
):
    conditions = crud.get_vehicle_conditions(db, vehicle_id=vehicle_id)
    return conditions


@router.patch("/vehicles/{plate_number}/registry-details", response_model=schemas.Vehicle)
def update_vehicle_registry_details(
        plate_number: str,
        registry_data: schemas.VehicleRegistryUpdate,
        current_user: models.RegistryWorker = Depends(get_current_registry_worker),
        db: Session = Depends(get_db)
):
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == plate_number
    ).first()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Update only the registry-specific fields
    update_data = registry_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vehicle, field, value)

    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.post("/vehicle-conditions/", response_model=schemas.VehicleCondition)
def create_vehicle_condition(
        condition: schemas.VehicleConditionCreate,
        current_user: models.RegistryWorker = Depends(get_current_registry_worker),
        db: Session = Depends(get_db)
):
    # Verify vehicle exists
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == condition.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return crud.create_vehicle_condition(db=db, condition=condition)


@router.get("/vehicles/{plate_number}/conditions", response_model=List[schemas.VehicleCondition])
def get_vehicle_conditions(
        plate_number: str,
        current_user: models.RegistryWorker = Depends(get_current_registry_worker),
        db: Session = Depends(get_db)
):
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == plate_number
    ).first()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    conditions = db.query(models.VehicleCondition).filter(
        models.VehicleCondition.vehicle_id == vehicle.id
    ).all()

    return conditions


# In routers/registry.py
@router.post("/vehicles/transfer-ownership", response_model=schemas.Vehicle)
async def transfer_vehicle_ownership(
        transfer_request: schemas.VehicleTransferRequest,  # We'll create this
        current_user: models.RegistryWorker = Depends(get_current_registry_worker),
        db: Session = Depends(get_db)
):
    """
    Transfer vehicle ownership from one user to another (registry worker only)
    """
    # Find the vehicle
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.plate_number == transfer_request.plate_number
    ).first()

    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )

    # Find the new owner
    new_owner = db.query(models.User).filter(
        models.User.id == transfer_request.new_user_id
    ).first()

    if not new_owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New owner not found"
        )

    # End current ownership if exists
    if vehicle.user_id:
        current_ownership = db.query(models.OwnershipHistory).filter(
            models.OwnershipHistory.vehicle_id == vehicle.id,
            models.OwnershipHistory.end_date == None
        ).first()

        if current_ownership:
            current_ownership.end_date = datetime.utcnow()

    # Transfer ownership
    old_user_id = vehicle.user_id
    vehicle.user_id = transfer_request.new_user_id

    # Create new ownership record
    new_ownership = models.OwnershipHistory(
        vehicle_id=vehicle.id,
        user_id=transfer_request.new_user_id,
        start_date=datetime.utcnow()
    )
    db.add(new_ownership)

    db.commit()
    db.refresh(vehicle)

    return vehicle
