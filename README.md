"# SolarTake" 

## 用 Docker 啟動（前端、後端和資料庫）

第一次使用時，先安裝並啟動 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，等待 Docker Desktop 顯示正在執行。接著在 PowerShell 切換到專案資料夾：

```powershell
cd C:\Users\Hyperian\Desktop\SolarTake
```

建立並啟動所有服務：

```powershell
docker compose up --build
```

首次執行會下載基礎映像並安裝套件，請等待終端機出現服務啟動訊息。完成後：

- 前端：<http://localhost:8501>
- 後端 API 文件：<http://localhost:8000/docs>
- 後端健康檢查：<http://localhost:8000/health>

要停止服務，在執行 `docker compose up` 的終端機按 `Ctrl+C`，再執行：

```powershell
docker compose down
```

資料庫資料會保存在 Docker volume 中；一般停止服務不會刪除資料。只有確定要清空資料庫時，才執行 `docker compose down -v`。

前端使用 `frontend/streamlit_app_v0.4.py`。後端與 PostgreSQL 會由 Compose 自動連接。LLM 金鑰可留空（使用示範模式）；若要啟用，請在專案根目錄的 `.env` 設定 `ANTHROPIC_API_KEY`。部署到公開或正式環境前，請在 `.env` 設定強而隨機的 `SECRET_KEY` 和 `POSTGRES_PASSWORD`；不要將 `.env` 分享或提交到版本控制。"
