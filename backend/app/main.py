from fastapi import FastAPI

app = FastAPI(title="太陽能裝設評估 API")

@app.get("/health")
def health_check():
    return {"status": "ok"}

from fastapi import FastAPI
from sqlalchemy import text
from app.db.base import Base
from app.db.session import engine
from app.models import user, assessment  # 匯入才會註冊資料表

app = FastAPI(title="Solar Assessment")

Base.metadata.create_all(bind=engine)  # MVP 階段先用這個自動建表

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"db": "ok"}

'''
FastAPI：建立網頁 API 的主類別。
text：SQLAlchemy 2.0 要求手寫的 SQL 字串必須用 text() 包起來。
匯入 Base 和 engine。
最後一行匯入 user、assessment 兩個模組。看起來沒用到，但不能刪：匯入時模組裡的 class User(Base) 
才會執行並登記到 Base.metadata，否則下面建表時 SQLAlchemy 不知道有這兩張表。

建立 app 實例，title 會顯示在 /docs 頁面。啟動指令 uvicorn app.main:app 的
最後一個 app 就是這個變數。

依照登記的所有 model，在資料庫建立還不存在的表。已存在的表不會被修改。
所以之後如果你改了欄位（例如新增一欄），這行不會幫你更新舊表，正式做法是用 Alembic 
做資料庫遷移，MVP 階段先用這個。

@app.get("/health")：裝飾器，代表「有人用 GET 請求 /health 時，執行下面這個函式」。
回傳的字典會自動轉成 JSON：{"status":"ok"}。
這個端點只確認 FastAPI 本身有在跑。

這個端點確認資料庫連得上。
with engine.connect() as conn：向資料庫要一條連線，with 結束時自動歸還。
conn.execute(text("SELECT 1"))：送出最簡單的 SQL，只是測試資料庫有沒有回應。
如果連不上（密碼錯、資料庫不存在），這裡會丟出錯誤，你會在瀏覽器看到 500，終端機會顯示原因。
成功才會回傳 {"db":"ok"}。
'''