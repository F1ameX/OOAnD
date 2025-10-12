import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

class n8nManager:
    def __init__(self):
        self.webhook_start = os.getenv("N8N_START_URL")
        self.webhook_enqueue = os.getenv("N8N_ENQUEUE_URL")
        self.webhook_autorun = os.getenv("N8N_AUTORUN_URL")
        self.auth = os.getenv("N8N_AUTH")

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.auth:
            headers["Authorization"] = self.auth
        return headers

    def _post(self, url: str, payload: dict) -> str:
        if not url:
            return "❌ Webhook URL не настроен."
        try:
            r = requests.post(url, headers=self._headers(), data=json.dumps(payload), timeout=20)
            if 200 <= r.status_code < 300:
                return "✅ Успешно отправлено в n8n."
            return f"⚠️ n8n ответил HTTP {r.status_code}: {r.text[:200]}"
        except requests.Timeout:
            return "⏱️ n8n: таймаут запроса."
        except Exception as e:
            return f"💥 Ошибка n8n: {e}"

    async def trigger_start(self, chat_id: int) -> str:
        """POST в webhook_start"""
        payload = {"trigger": "manual", "chat_id": chat_id}
        return self._post(self.webhook_start, payload)

    async def trigger_enqueue(self, chat_id: int, url: str) -> str:
        """POST в webhook_enqueue"""
        payload = {"url": url, "chat_id": chat_id}
        return self._post(self.webhook_enqueue, payload)

    async def trigger_autorun(self, chat_id: int, action: str, minutes: int | None = None) -> str:
        """POST в webhook_autorun"""
        payload = {"chat_id": chat_id, "action": action}
        if action == "start" and minutes:
            payload["minutes"] = minutes
        return self._post(self.webhook_autorun, payload)