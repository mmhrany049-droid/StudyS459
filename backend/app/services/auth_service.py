from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone
from ..models.user import User
from ..config.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def get_user_by_username_or_email(db: Session, identifier: str):
    return db.query(User).filter(or_(User.username == identifier, User.email == identifier)).first()

def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def authenticate_user(db: Session, identifier: str, password: str):
    user = get_user_by_username_or_email(db, identifier)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_user(db: Session, email: str, username: str, password: str, full_name: str | None = None):
    # check duplicates
    existing = db.query(User).filter(or_(User.email == email, User.username == username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email or username already exists")
    hashed = get_password_hash(password)
    user = User(email=email, username=username, hashed_password=hashed, full_name=full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
