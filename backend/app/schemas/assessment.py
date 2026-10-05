from pydantic import BaseModel, ConfigDict
from datetime import datetime

# 1. 前端發起「太陽能評估」時傳進來的 Request 格式
class AssessmentCreate(BaseModel):
    address: str                     # 必填：裝設地址
    latitude: float | None = None    # 選填：緯度
    longitude: float | None = None   # 選填：經度

# 2. 回傳給前端的評估結果 Response 格式
class AssessmentResponse(BaseModel):
    id: int
    user_id: int
    address: str
    latitude: float | None
    longitude: float | None
    status: str                      # 評估狀態 (如 pending, completed)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    