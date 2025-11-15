from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import crud
import models
import schemas
from auth import get_db

router = APIRouter(prefix="/users", tags=["vehicle_search"])


@router.get("/vehicles/search/{plate}", response_model=schemas.VehicleSearchResult)
def search_vehicle(
        plate: str, db: Session = Depends(get_db)):
    vehicle = crud.get_vehicle_by_plate(db, plate_number=plate)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Get related data
    accidents = db.query(models.Accident).filter(models.Accident.vehicle_id == vehicle.id).all()
    ownership_history = db.query(models.OwnershipHistory).filter(
        models.OwnershipHistory.vehicle_id == vehicle.id
    ).all()
    tickets = db.query(models.Ticket).filter(models.Ticket.vehicle_id == vehicle.id).all()
    parking_sessions = db.query(models.ParkingSession).filter(
        models.ParkingSession.vehicle_id == vehicle.id
    ).all()
    conditions = crud.get_vehicle_conditions(db, vehicle_id=vehicle.id)

    return schemas.VehicleSearchResult(
        vehicle=vehicle,
        accidents=accidents,
        ownership_history=ownership_history,
        tickets=tickets,
        parking_sessions=parking_sessions,
        conditions=conditions
    )
