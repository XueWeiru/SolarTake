from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime

# 1. 前端「註冊/建立使用者」時傳進來的 Request Body 格式
class UserCreate(BaseModel):
    email: EmailStr                  # 自動驗證是否為合法 Email 格式
    password: str                    # 原始密碼（將在 Service 層進行 Hash 加密）
    full_name: str | None = None     # 選填欄位，預設為 None

# 2. API 「回傳給前端」的 Response 格式（排除敏感的 password）
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    created_at: datetime

    # 使用 Pydantic v2 的 ConfigDict 設定
    # from_attributes=True 讓 Pydantic 可以直接讀取 SQLAlchemy ORM 物件並自動轉成 JSON
    model_config = ConfigDict(from_attributes=True)
