import requests
from app.core.config import settings

key = settings.ANTHROPIC_API_KEY
print("長度:", len(key), "| 結尾字元:", repr(key[-1]), "| 前後有空白:", key != key.strip())

r = requests.post(
    "https://api.anthropic.com/v1/messages",
    headers={
        "x-api-key": key.strip(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    },
    json={
        "model": "claude-sonnet-4-6",
        "max_tokens": 50,
        "messages": [{"role": "user", "content": "你好"}],
    },
    timeout=30,
)
print(r.status_code)
print(r.text[:300])