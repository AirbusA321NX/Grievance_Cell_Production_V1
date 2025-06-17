from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer , HTTPBearer , HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from database import get_db
from User import models
from roles import RoleEnum as Role
from typing import List
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = HTTPBearer()

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Secret key and algorithm for JWT decoding (replace with your own secure key)


def get_db_session():
    return get_db()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    token = credentials.credentials  # Extract the actual bearer token
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_raw = payload.get("sub")
        if user_id_raw is None or not str(user_id_raw).isdigit():
            raise credentials_exception
        user_id = int(user_id_raw)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    return current_user

class RoleChecker:
    def __init__(self, allowed_roles: List[Role]):
        self.allowed_roles = [role.value if isinstance(role, Role) else role for role in allowed_roles]

    def __call__(self, current_user: models.User = Depends(get_current_active_user)):
        if current_user.role not in self.allowed_roles:
            print(11111)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        return current_user
