from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "change-me"

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

settings = Settings()

'''
Path：Python 內建，用來處理檔案路徑。
BaseSettings：pydantic-settings 提供的類別，繼承它就能自動從環境變數或 .env 讀值。
SettingsConfigDict：用來設定 BaseSettings 的行為。

__file__：目前這個檔案的路徑（backend/app/core/config.py）。
.resolve()：轉成完整的絕對路徑。
.parents[3]：往上找第 4 層資料夾。parents[0] 是 core，[1] 是 app，[2] 是 backend，[3] 是專案根目錄 solar-assessment。
/ ".env"：接上檔名，得到 solar-assessment/.env。
這樣不管你在哪個資料夾執行 uvicorn，都能找到 .env。

定義一個設定類別，每個欄位對應 .env 裡同名的變數。
DATABASE_URL: str：沒有預設值，代表必填，.env 沒寫就會報錯。
SECRET_KEY: str = "change-me"：有預設值，沒設定時用 "change-me"。

env_file=ENV_FILE：指定要讀哪個 .env。
extra="ignore"：.env 裡有 Settings 沒定義的變數時直接忽略，不報錯。

建立一個實例，此時會真的去讀 .env。其他檔案用 from app.core.config import settings 就能取用。
'''