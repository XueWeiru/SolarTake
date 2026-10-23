from functools import lru_cache # 加入 LLM service 的依賴

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.security import decode_access_token
from app.db.session import get_db
from app.repositories import user_repository
from app.models.user import User

from app.services.llm_service import LLMService # 加入 LLM service 的依賴

bearer_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    user_id = decode_access_token(credentials.credentials)
    user = user_repository.get_by_id(db, user_id) if user_id else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登入或 token 已失效")
    return user

@lru_cache
def get_llm_service() -> LLMService:
    return LLMService()