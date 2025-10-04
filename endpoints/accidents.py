# Create routers/accidents.py
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import crud
import models
import schemas, schemas_accident
from auth import get_current_user, get_db
from fastapi import File, UploadFile
import shutil
import os


router = APIRouter(prefix="/accidents", tags=["accidents"])


@router.post("/report", response_model=schemas_accident.AccidentUser)
async def report_accident(
        accident_data: schemas.AccidentCreate,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Report a new accident with multiple vehicles and images
    """
    try:
        # Validate that at least 2 vehicles are involved
        if len(accident_data.vehicles) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least 2 vehicles must be involved in an accident"
            )

        # Validate that exactly one vehicle is at fault
        at_fault_count = sum(1 for v in accident_data.vehicles if v.is_at_fault)
        if at_fault_count != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exactly one vehicle must be marked as at fault"
            )

        # Validate images (at least 8 as requested)
        if len(accident_data.images) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least 8 accident images are required"
            )

        accident = crud.create_accident_report(db, accident_data, current_user.id)
        return accident

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{docket_number}", response_model=schemas_accident.AccidentUser)
async def get_accident(
        docket_number: str,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get accident details by police docket number
    """
    accident = crud.get_accident_by_docket(db, docket_number)
    if not accident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accident not found"
        )
    return accident


@router.get("/my-accidents", response_model=List[schemas_accident.AccidentUser])
async def get_my_accidents(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get all accidents involving the current user's vehicles
    """
    return crud.get_user_accidents(db, current_user.id)


@router.post("/{docket_number}/confirm", response_model=schemas_accident.AccidentConfirmation)
async def confirm_accident(
        docket_number: str,
        confirmation_data: schemas_accident.AccidentConfirmationCreate,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Confirm or dispute an accident report (for involved parties)
    """
    accident = crud.get_accident_by_docket(db, docket_number)
    if not accident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accident not found"
        )

    try:
        confirmation = crud.create_accident_confirmation(
            db, accident.id, current_user.id, confirmation_data
        )
        return confirmation
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

UPLOAD_DIR = "uploads/accidents"


@router.post("/upload-images")
async def upload_accident_images(
        files: List[UploadFile] = File(...),
        current_user: models.User = Depends(get_current_user)
):
    """
    Upload accident images and return their URLs
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    uploaded_urls = []
    for file in files:
        # Generate unique filename
        file_extension = file.filename.split('.')[-1]
        unique_filename = f"{current_user.id}_{datetime.utcnow().timestamp()}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Store relative URL (you might want to use a CDN in production)
        uploaded_urls.append(f"/{file_path}")

    return {"image_urls": uploaded_urls}
