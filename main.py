from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from auth import (
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    authenticate_parking_worker,
    authenticate_police,
    authenticate_registry_worker
)
from datetime import timedelta
from sqlalchemy.orm import Session
from database import get_db
import models
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import engine, Base
import models


# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CarTrack System",
              description="Vehicle Management System",
              version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Import all routers
from endpoints import (
    parking,
    police,
    registry,
    tolls,
    users,
    borrow,
    email
)

app.include_router(users.router, prefix="/api")
app.include_router(borrow.router, prefix="/api")
app.include_router(parking.router, prefix="/api")
app.include_router(police.router, prefix="/api")
app.include_router(registry.router, prefix="/api")
app.include_router(tolls.router, prefix="/api")
# app.include_router(email.router, prefix="/api")


async def authenticate_any_user(db: Session, username: str, password: str):
    """Try authenticating as any user type"""
    auth_functions = [
        authenticate_user,
        authenticate_parking_worker,
        authenticate_police,
        authenticate_registry_worker
    ]

    for auth_func in auth_functions:
        user = await auth_func(db, username, password)
        if user:
            return user
    return None


@app.post("/auth/token", tags=["Authentication"])
async def login_for_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)
):
    """Get access token for API authentication (all user types)"""
    user = await authenticate_any_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Determine user type and include relevant data
    user_data = {"sub": user.username}
    if hasattr(user, 'employee_id'):
        user_data["employee_id"] = user.employee_id
        if hasattr(user, 'zone'):  # Parking worker
            user_data.update({
                "role": "parking_worker",
                "zone": user.zone
            })
        else:  # Registry worker
            user_data["role"] = "registry_worker"
    elif hasattr(user, 'badge_number'):  # Police
        user_data.update({
            "role": "police",
            "badge_number": user.badge_number,
            "station": user.station
        })
    else:  # Regular user
        user_data.update({
            "role": "user",
            "user_id": user.id
        })

    access_token = create_access_token(
        data=user_data,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer", "user_type": user_data["role"]}


@app.post("/login", response_class=HTMLResponse, tags=["Authentication"])
async def login_for_web(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    """Web login endpoint that sets authentication cookie"""
    user = await authenticate_any_user(db, username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid credentials"
        }, status_code=400)

    # Simplified token for web (no role-specific data needed)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=False  # Set to True in production with HTTPS
    )
    return response


@app.get("/protected", tags=["Test"])
async def protected_route(user: models.User = Depends(get_current_user)):
    """Example protected endpoint that requires authentication"""
    return {"message": "You're authenticated!", "user": user.username}


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint that provides system information"""
    return {
        "message": "Welcome to CarTrack System",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }
