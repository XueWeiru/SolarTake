from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

'''
匯入建立連線引擎、建立 session 工廠的工具，以及剛才的 settings。

engine 是到資料庫的連線入口，內部管理連線池。
它用 .env 的 DATABASE_URL 知道要連哪個資料庫、用什麼帳號。
建立 engine 時還沒真正連線，第一次查詢才會連。

sessionmaker 是「session 工廠」，呼叫 SessionLocal() 就產生一個新的 session（一次對話）。
bind=engine：這些 session 都用上面的 engine 連線。
autoflush=False：不要在查詢前自動把未送出的變更寫進資料庫，由你自己控制。
autocommit=False：改動要自己呼叫 commit() 才會生效。

這是 FastAPI 的「依賴」函式，之後每個 API 會用 Depends(get_db) 取得資料庫 session。
db = SessionLocal()：開一個 session。
yield db：把 session 交給 API 使用，API 跑完後程式會回到這裡繼續。
finally: db.close()：不管 API 成功或出錯，最後一定關閉 session，避免連線洩漏。
'''