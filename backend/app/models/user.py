from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    assessments = relationship("Assessment", back_populates="user")

'''
datetime：Python 的時間型別，用來標註 created_at。
String、DateTime：資料庫欄位型別。
func：呼叫資料庫函式，如 now()。
Mapped、mapped_column：SQLAlchemy 2.0 的欄位宣告方式。
relationship：宣告表與表之間的關聯。

繼承 Base，代表這是一張資料表。
__tablename__：資料庫裡實際的表名叫 users。

整數欄位，是主鍵（每筆資料的唯一編號）。PostgreSQL 會自動遞增：1、2、3⋯

最長 255 字元的字串。
unique=True：不允許兩個人用同一個 email 註冊。
index=True：建立索引，登入時用 email 查人會更快。

存密碼雜湊值，不是明文密碼。

str | None 表示可以是空值（資料庫欄位允許 NULL），使用者可以不填名字。

建立時間。server_default=func.now() 是讓資料庫在新增時自動填入當下時間，你不用手動給值。

這不是資料表欄位，而是 Python 端的便利關聯：user.assessments 可以取得這個使用者的所有評估紀錄。
"Assessment" 用字串，是因為那個類別在另一個檔案，用字串可以延後解析。
back_populates="user"：對應 Assessment 裡的 user，兩邊互相連動。
'''