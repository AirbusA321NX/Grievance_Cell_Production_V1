from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta


from database import get_db
from User import crud, schemas
from dependencies import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from roles import RoleEnum

router = APIRouter(tags=["Authentication"])

@router.post("/signup", response_model=schemas.UserFull, status_code=status.HTTP_201_CREATED)
def signup(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = crud.get_users(db, role_filter=None)
    if any(u.email == user_in.email for u in existing):
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db, user_in)

@router.post("/login", summary="Login and get JWT")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}
