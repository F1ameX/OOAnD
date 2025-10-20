import json
import os
import base64
import requests
from pathlib import Path

from googleapiclient.discovery import build
from gspread import service_account


class apiManager:
    def __init__(self, secrets_path: str = "secrets.json"):
        self.secrets_path = Path(secrets_path)
        self.data = {}
        self._load()

    # ---------- persistence ----------
    def _load(self):
        try:
            if self.secrets_path.exists():
                self.data = json.loads(self.secrets_path.read_text(encoding="utf-8"))
            else:
                self.data = {}
        except Exception:
            self.data = {}

    def _save(self):
        if self.secrets_path.parent:
            self.secrets_path.parent.mkdir(parents=True, exist_ok=True)
        self.secrets_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def merge_and_save(self, payload: dict) -> dict:
        updated, ignored, errors = [], [], []
        if not isinstance(payload, dict):
            return {"updated": [], "ignored": [], "errors": ["payload is not dict"]}

        allowed = {"n8n", "youtube", "sheets", "cloudinary", "swiftia", "gemini"}
        for section, content in payload.items():
            if section not in allowed or not isinstance(content, dict):
                ignored.append(section)
                continue
            if section not in self.data or not isinstance(self.data.get(section), dict):
                self.data[section] = {}
            for k, v in content.items():
                self.data[section][k] = v
                updated.append(f"{section}.{k}")

        try:
            self._save()
        except Exception as e:
            errors.append(str(e))

        return {"updated": updated, "ignored": ignored, "errors": errors}

    # ---------- health checks ----------
    def health_all(self, fallback_channel_id: str = "") -> dict:
        return {
            "n8n": self.health_n8n(),
            "youtube": self.health_youtube(fallback_channel_id=fallback_channel_id),
            "sheets": self.health_sheets(),
            "cloudinary": self.health_cloudinary(),
            "swiftia": self.health_swiftia(),
            "gemini": self.health_gemini(),
            "all_ok": False,  # заполним ниже
        } | self._finalize()

    def _finalize(self) -> dict:
        # Вынесено, чтобы выставить all_ok после сборки
        return {}

    # n8n: POST на каждый вебхук с маленьким payload
    def health_n8n(self) -> dict:
        """
        Проверяем доступность вебхуков n8n.
        Приоритет: test-эндпоинты -> боевые.
        Возвращаем подробный статус по каждому.
        """
        cfg = self.data.get("n8n", {})
        # prod из secrets.json ИЛИ .env
        prod_start   = cfg.get("webhook_start")    or os.getenv("N8N_START_URL")
        prod_enqueue = cfg.get("webhook_enqueue")  or os.getenv("N8N_ENQUEUE_URL")
        prod_autorun = cfg.get("webhook_autorun")  or os.getenv("N8N_AUTORUN_URL")
        auth         = cfg.get("auth")             or os.getenv("N8N_AUTH")

        # test-URL либо в том же блоке n8n, новыми ключами:
        test_start   = cfg.get("webhook_start_test")   or os.getenv("N8N_START_URL_TEST")
        test_enqueue = cfg.get("webhook_enqueue_test") or os.getenv("N8N_ENQUEUE_URL_TEST")
        test_autorun = cfg.get("webhook_autorun_test") or os.getenv("N8N_AUTORUN_URL_TEST")

        def _ping(url, *, is_test: bool):
            if not url:
                return {"ok": False, "detail": "no url", "mode": "test" if is_test else "prod"}
            try:
                headers = {"Content-Type": "application/json"}
                if auth:
                    headers["Authorization"] = auth
                # тестовый эндпоинт лучше пинговать POST-ом с безвредным payload
                r = requests.post(url, json={"ping": True}, headers=headers, timeout=10)
                ok = 200 <= r.status_code < 300
                detail = f"http {r.status_code}"
                # популярный кейс n8n: 404 на /webhook-test если воркфлоу не в Test Mode
                if is_test and r.status_code == 404:
                    detail = "404 (workflow not in Test mode?)"
                return {"ok": ok, "detail": detail, "mode": "test" if is_test else "prod"}
            except requests.Timeout:
                return {"ok": False, "detail": "timeout", "mode": "test" if is_test else "prod"}
            except Exception as e:
                return {"ok": False, "detail": str(e), "mode": "test" if is_test else "prod"}

        # для каждого типа выбираем: test если есть, иначе prod
        rs = {
            "start":   _ping(test_start   or prod_start,   is_test=bool(test_start)),
            "enqueue": _ping(test_enqueue or prod_enqueue, is_test=bool(test_enqueue)),
            "autorun": _ping(test_autorun or prod_autorun, is_test=bool(test_autorun)),
        }
        all_ok = all(v["ok"] for v in rs.values())
        return {"ok": all_ok, **rs}
    
    # YouTube: реальный вызов
    def health_youtube(self, *, fallback_channel_id: str = "") -> dict:
        cfg = self.data.get("youtube", {})
        api_key = os.getenv("YOUTUBE_API_KEY") or cfg.get("api_key")
        channel_id = os.getenv("YOUTUBE_CHANNEL_ID") or cfg.get("channel_id") or fallback_channel_id
        if not api_key:
            return {"ok": False, "detail": "no api_key"}
        if not channel_id:
            return {"ok": False, "detail": "no channel_id"}

        try:
            yt = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
            resp = yt.channels().list(id=channel_id, part="id").execute()
            items = resp.get("items", [])
            return {"ok": bool(items), "detail": "reachable" if items else "channel not found"}
        except Exception as e:
            return {"ok": False, "detail": f"{e}"}

    # Sheets: gspread — открыть и получить значения
    def health_sheets(self) -> dict:
        cfg = self.data.get("sheets", {})
        sa_file = os.getenv("FILE_LOCATION") or cfg.get("service_account_file")
        url = os.getenv("TABLE_LINK") or cfg.get("spreadsheet_url")
        if not sa_file:
            return {"ok": False, "detail": "no service_account_file"}
        if not url:
            return {"ok": False, "detail": "no spreadsheet_url"}

        try:
            gc = service_account(filename=sa_file)
            book = gc.open_by_url(url)
            ws = book.sheet1
            _ = ws.get_all_values()
            return {"ok": True, "detail": "reachable"}
        except Exception as e:
            return {"ok": False, "detail": f"{e}"}

    # Cloudinary: /ping
    def health_cloudinary(self) -> dict:
        cfg = self.data.get("cloudinary", {})
        cloud_name = cfg.get("cloud_name")
        api_key = cfg.get("api_key")
        api_secret = cfg.get("api_secret")

        if not (cloud_name and api_key and api_secret):
            return {"ok": False, "detail": "not configured"}

        try:
            url = f"https://api.cloudinary.com/v1_1/{cloud_name}/ping"
            basic = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
            r = requests.get(url, headers={"Authorization": f"Basic {basic}"}, timeout=10)
            return {"ok": 200 <= r.status_code < 300, "detail": f"http {r.status_code}"}
        except Exception as e:
            return {"ok": False, "detail": f"{e}"}

    # Swiftia: GET base_url
    def health_swiftia(self) -> dict:
        cfg = self.data.get("swiftia", {})
        base_url = cfg.get("base_url")
        auth = cfg.get("auth")
        if not base_url:
            return {"ok": False, "detail": "not configured"}
        try:
            headers = {"Authorization": auth} if auth else {}
            r = requests.get(base_url, headers=headers, timeout=10)
            return {"ok": 200 <= r.status_code < 300, "detail": f"http {r.status_code}"}
        except Exception as e:
            return {"ok": False, "detail": f"{e}"}

    # Gemini: GET models
    def health_gemini(self) -> dict:
        cfg = self.data.get("gemini", {})
        api_key = cfg.get("api_key")
        if not api_key:
            return {"ok": False, "detail": "not configured"}
        try:
            r = requests.get(
                "https://generativelanguage.googleapis.com/v1/models",
                params={"key": api_key},
                timeout=10
            )
            return {"ok": 200 <= r.status_code < 300, "detail": f"http {r.status_code}"}
        except Exception as e:
            return {"ok": False, "detail": f"{e}"}
