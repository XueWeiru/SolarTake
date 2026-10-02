from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Assessment(Base):
    __tablename__ = "assessments"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    address: Mapped[str] = mapped_column(String(500))

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    user = relationship("User", back_populates="assessments")

'''
比 user 多了 ForeignKey（外鍵）和 Float（小數）。

表名 assessments，主鍵 id，同上。

外鍵：這筆評估屬於哪個使用者。
"users.id" 是「users 表的 id 欄位」，資料庫會確保這個值必須真的存在於 users 表。

使用者輸入的地址，最長 500 字元，必填。

緯度、經度，可為空。因為現在只存地址，之後才會做「地址轉經緯度」，所以先允許空值。

狀態欄位，例如 pending（等待處理）。
注意這裡是 default，和 created_at 的 server_default 不同：default 是 Python 端新增資料時幫你填，server_default 是資料庫端填。

建立時間，同 user。

assessment.user 可以取得這筆評估所屬的使用者物件，和 User.assessments 是一對。
'''
