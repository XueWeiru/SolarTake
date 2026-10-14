from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import hash_password, verify_password, create_access_token
from app.repositories import user_repository
from app.schemas.user import UserCreate, UserLogin
from app.models.user import User

def register(db: Session, data: UserCreate) -> User:
    email = data.email.lower()
    if user_repository.get_by_email(db, email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "此 Email 已被註冊")
    return user_repository.create(
        db, email=email, password_hash=hash_password(data.password), full_name=data.full_name
    )

def login(db: Session, data: UserLogin) -> str:
    user = user_repository.get_by_email(db, data.email.lower())
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email 或密碼錯誤")
    return create_access_token(user.id)