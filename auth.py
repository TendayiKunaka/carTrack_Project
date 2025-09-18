from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from database import get_db
import models
from passlib.context import CryptContext
import logging
# Add this at the top
from typing import Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from passlib.context import CryptContext

# Configuration
SECRET_KEY = "your-secret-key-please-change-this"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Password utilities (add these)
def get_password_hash(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


# ... rest of your auth.py code ...
logger = logging.getLogger(__name__)


# In auth.py

async def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return False
    if not pwd_context.verify(password, user.hashed_password):
        return False
    return user


async def authenticate_parking_worker(db: Session, username: str, password: str):
    worker = db.query(models.ParkingWorker).filter(models.ParkingWorker.username == username).first()
    if not worker:
        return False
    if not pwd_context.verify(password, worker.hashed_password):
        return False
    return worker


async def authenticate_police(db: Session, username: str, password: str):
    officer = db.query(models.Police).filter(models.Police.username == username).first()
    if not officer:
        return False
    if not pwd_context.verify(password, officer.hashed_password):
        return False
    return officer


async def authenticate_registry_worker(db: Session, username: str, password: str):
    worker = db.query(models.RegistryWorker).filter(models.RegistryWorker.username == username).first()
    if not worker:
        return False
    if not pwd_context.verify(password, worker.hashed_password):
        return False
    return worker


async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)
):
    # Try all authentication methods with proper await
    auth_attempts = [
        ("user", authenticate_user),
        ("parking_worker", authenticate_parking_worker),
        ("police", authenticate_police),
        ("registry_worker", authenticate_registry_worker)
    ]

    for role, auth_func in auth_attempts:
        auth_result = await auth_func(db, form_data.username, form_data.password)
        if auth_result:
            # Common fields
            user_data = {"sub": auth_result.username, "role": role}

            # Role-specific fields
            if role == "user":
                user_data["user_id"] = auth_result.id
            elif role == "parking_worker":
                user_data.update({
                    "zone": auth_result.zone,
                    "employee_id": auth_result.employee_id
                })
            elif role == "police":
                user_data.update({
                    "badge_number": auth_result.badge_number,
                    "station": auth_result.station
                })
            elif role == "registry_worker":
                user_data["employee_id"] = auth_result.employee_id

            # Generate token
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data=user_data,
                expires_delta=access_token_expires
            )

            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user_type": role
            }

    # If all attempts failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# Current user dependencies
async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Check all user types
    user_types = [
        models.User,
        models.ParkingWorker,
        models.Police,
        models.RegistryWorker
    ]

    for model in user_types:
        user = db.query(model).filter(model.username == username).first()
        if user:
            return user

    raise credentials_exception


# Role-specific dependencies
async def get_current_police(
        current_user: models.Police = Depends(get_current_user)
):
    if not isinstance(current_user, models.Police):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as police officer"
        )
    return current_user


async def get_current_parking_worker(
        current_user: models.ParkingWorker = Depends(get_current_user)
):
    if not isinstance(current_user, models.ParkingWorker):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as parking worker"
        )
    return current_user


async def get_current_registry_worker(
        current_user: models.RegistryWorker = Depends(get_current_user)
):
    if not isinstance(current_user, models.RegistryWorker):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as registry worker"
        )
    return current_user
