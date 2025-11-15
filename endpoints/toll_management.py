from datetime import datetime, timedelta  # Correct import

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
import secrets
import string

import crud
import models
import schemas
from auth import get_current_user, get_db

router = APIRouter(prefix="/tolls", tags=["toll_management"])


# Helper function to generate keypass code
def generate_keypass_code(length=12):
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


@router.post("/gates/", response_model=schemas.TollGate)
def create_toll_gate(
        toll_gate: schemas.TollGateCreate,
        db: Session = Depends(get_db)
):
    """
    Create a new toll gate
    """
    # Check if toll gate with same name already exists
    existing_gate = db.query(models.TollGate).filter(
        models.TollGate.name == toll_gate.name
    ).first()

    if existing_gate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Toll gate with this name already exists"
        )

    db_toll = models.TollGate(
        name=toll_gate.name,
        location=toll_gate.location,
        amount=toll_gate.amount
    )
    db.add(db_toll)
    db.commit()
    db.refresh(db_toll)
    return db_toll


@router.get("/all_gates/", response_model=List[schemas.TollGate])
def get_all_toll_gates(db: Session = Depends(get_db)):
    """
    Get all toll gates
    """
    return db.query(models.TollGate).all()


@router.post("/routes/", response_model=schemas.TollRoute)
def create_toll_route(
        route: schemas.TollRouteCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    # Check if user is admin (you might want to add admin check)

    # Create the route
    db_route = models.TollRoute(
        name=route.name,
        description=route.description
    )
    db.add(db_route)
    db.commit()
    db.refresh(db_route)

    # Add toll gates to route in order
    for order, toll_gate_id in enumerate(route.toll_gate_ids, 1):
        # Check if toll gate exists
        toll_gate = db.query(models.TollGate).filter(models.TollGate.id == toll_gate_id).first()
        if not toll_gate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Toll gate with ID {toll_gate_id} not found"
            )

        db_toll_gate_route = models.TollGateRoute(
            route_id=db_route.id,
            toll_gate_id=toll_gate_id,
            order=order
        )
        db.add(db_toll_gate_route)

    db.commit()

    # Refresh and load relationships to calculate total_amount
    db.refresh(db_route)

    # Eager load the toll_gates relationship to calculate total_amount
    db_route = db.query(models.TollRoute).options(
        joinedload(models.TollRoute.toll_gates).joinedload(models.TollGateRoute.toll_gate)
    ).filter(models.TollRoute.id == db_route.id).first()

    return db_route


@router.get("/all_routes/", response_model=List[schemas.TollRoute])
def get_all_toll_routes(db: Session = Depends(get_db)):
    # Eager load the relationships to calculate total_amount
    routes = db.query(models.TollRoute).options(
        joinedload(models.TollRoute.toll_gates).joinedload(models.TollGateRoute.toll_gate)
    ).all()
    return routes
