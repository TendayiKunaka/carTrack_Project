from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from database import get_db
import models
from typing import Optional
from models import ParkingWorker
from passlib.context import CryptContext

# Configuration
SECRET_KEY = "your-secret-key-please-change-this"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def get_user_role(db: Session, username: str) -> Optional[str]:
    """
    Returns the role of a user by checking all role tables
    """
    # Check if user is a regular user
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
        return "user"

    # Check if user is a parking worker
    parking_worker = db.query(models.ParkingWorker).filter(models.ParkingWorker.username == username).first()
    if parking_worker:
        return "parking_worker"

    # Check if user is a police officer
    police = db.query(models.Police).filter(models.Police.username == username).first()
    if police:
        return "police"

    # Check if user is a registry worker
    registry_worker = db.query(models.RegistryWorker).filter(models.RegistryWorker.username == username).first()
    if registry_worker:
        return "registry_worker"

    return None


# Then update authenticate_user function:
def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return False
    if not pwd_context.verify(password, user.hashed_password):
        return False
    return user


def authenticate_parking_worker(db: Session, username: str, password: str):
    worker = db.query(models.ParkingWorker).filter(models.ParkingWorker.username == username).first()
    if not worker:
        return False
    if not pwd_context.verify(password, worker.hashed_password):
        return False
    return worker
'''async def authenticate_parking_worker(db: Session, username: str, password: str):
    worker = db.query(models.ParkingWorker).filter(models.ParkingWorker.username == username).first()
    if not worker:
        print(f"No worker found with username: {username}")
        return False

    # Add debug print to see the stored hash and input password
    print(f"Stored hash: {worker.hashed_password}")
    print(f"Input password: {password}")

    # Verify the password
    is_valid = pwd_context.verify(password, worker.hashed_password)
    print(f"Password valid: {is_valid}")

    if not is_valid:
        return False
    return worker'''


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


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
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
        return user

    worker = db.query(models.ParkingWorker).filter(models.ParkingWorker.username == username).first()
    if worker:
        return worker

    police = db.query(models.Police).filter(models.Police.username == username).first()
    if police:
        return police

    registry = db.query(models.RegistryWorker).filter(models.RegistryWorker.username == username).first()
    if registry:
        return registry

    raise credentials_exception


async def get_current_police(
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
        role: str = payload.get("role")
        if username is None or role != "police":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    officer = db.query(models.Police).filter(models.Police.username == username).first()
    if officer is None:
        raise credentials_exception
    return officer


async def get_current_registry_worker(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    worker = db.query(models.RegistryWorker).filter(
        models.RegistryWorker.username == current_user.username
    ).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as registry worker"
        )
    return worker


async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Try authenticating as parking worker first
    worker = await authenticate_parking_worker(db, form_data.username, form_data.password)
    if worker:
        user_data = {
            "sub": worker.username,
            "role": "parking_worker",
            "zone": worker.zone,
            "employee_id": worker.employee_id
        }
        user_type = "parking_worker"
    else:
        # If not parking worker, try regular user
        user = authenticate_user(db, form_data.username, form_data.password)
        if user:
            user_data = {
                "sub": user.username,
                "role": "user",
                "user_id": user.id
            }
            user_type = "user"
        else:
            # If not regular user, try police officer
            police = await authenticate_police(db, form_data.username, form_data.password)
            if police:
                user_data = {
                    "sub": police.username,
                    "role": "police",
                    "badge_number": police.badge_number,
                    "station": police.station
                }
                user_type = "police"
            else:
                # Finally, try registry worker
                registry = await authenticate_registry_worker(db, form_data.username, form_data.password)
                if registry:
                    user_data = {
                        "sub": registry.username,
                        "role": "registry_worker",
                        "employee_id": registry.employee_id
                    }
                    user_type = "registry_worker"
                else:
                    # If none match, reject login
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Incorrect username or password",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

    # Generate token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data=user_data,
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": user_type
    }

async def login_for_access_token2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Try authenticating as regular user first
    user = authenticate_user(db, form_data.username, form_data.password)
    if user:
        user_data = {
            "sub": user.username,
            "role": "user",
            "user_id": user.id
        }
        user_type = "user"
    else:
        # Try authenticating as parking worker
        worker = await authenticate_parking_worker(db, form_data.username, form_data.password)
        if worker:
            user_data = {
                "sub": worker.username,
                "role": "parking_worker",
                "zone": worker.zone,
                "employee_id": worker.employee_id
            }
            user_type = "parking_worker"
        else:
            # Try authenticating as police officer
            police = await authenticate_police(db, form_data.username, form_data.password)
            if police:
                user_data = {
                    "sub": police.username,
                    "role": "police",
                    "badge_number": police.badge_number,
                    "station": police.station
                }
                user_type = "police"
            else:
                # Finally, try registry worker
                registry = await authenticate_registry_worker(db, form_data.username, form_data.password)
                if registry:
                    user_data = {
                        "sub": registry.username,
                        "role": "registry_worker",
                        "employee_id": registry.employee_id
                    }
                    user_type = "registry_worker"
                else:
                    # If none match, reject login
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Incorrect username or password",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

    # Generate token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data=user_data,
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": user_type
    }


async def get_current_parking_worker(
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
        role: str = payload.get("role")
        if username is None or role != "parking_worker":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    worker = db.query(models.ParkingWorker).filter(models.ParkingWorker.username == username).first()
    if worker is None:
        raise credentials_exception
    return worker


async def authenticate_registry_worker(db: Session, username: str, password: str):
    worker = db.query(models.RegistryWorker).filter(models.RegistryWorker.username == username).first()
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
