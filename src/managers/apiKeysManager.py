import json
import os
from pathlib import Path
import requests
from googleapiclient.discovery import build
from gspread import service_account


class apiManager:
    def __init__(self, secrets_path: str = "secrets.json"):
        self.secrets_path = Path(secrets_path)
        self.data = {}
        self._load()

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

    def health_all(self, fallback_channel_id: str = "") -> dict:
        n8n = self.health_n8n()
        yt = self.health_youtube(fallback_channel_id=fallback_channel_id)
        sh = self.health_sheets()
        cloud = self.health_cloudinary()
        swift = self.health_swiftia()
        gem = self.health_gemini()
        all_ok = all(s.get("ok", False) for s in [n8n, yt, sh, cloud, swift, gem])
        return {
            "n8n": n8n,
            "youtube": yt,
            "sheets": sh,
            "cloudinary": cloud,
            "swiftia": swift,
            "gemini": gem,
            "all_ok": all_ok,
        }

    def health_human(self, fallback_channel_id: str = "") -> str:
        res = self.health_all(fallback_channel_id=fallback_channel_id)
        lines = []
        lines.append(f"N8N_TEST_URL: {'OK' if res['n8n']['ok'] else 'FAIL'} ({res['n8n'].get('detail','')})")
        lines.append(f"YouTube: {'OK' if res['youtube']['ok'] else 'FAIL'} ({res['youtube'].get('detail','')})")
        lines.append(f"Sheets: {'OK' if res['sheets']['ok'] else 'FAIL'} ({res['sheets'].get('detail','')})")
        lines.append(f"Cloudinary: {'OK' if res['cloudinary']['ok'] else 'FAIL'} ({res['cloudinary'].get('detail','')})")
        lines.append(f"Swiftia: {'OK' if res['swiftia']['ok'] else 'FAIL'} ({res['swiftia'].get('detail','')})")
        lines.append(f"Gemini: {'OK' if res['gemini']['ok'] else 'FAIL'} ({res['gemini'].get('detail','')})")
        lines.append(f"Overall: {'OK' if res['all_ok'] else 'FAIL'}")
        return "\n".join(lines)

    def health_n8n(self) -> dict:
        test_url = os.getenv("N8N_TEST_URL")
        if not test_url:
            return {"ok": False, "detail": "N8N_TEST_URL not set"}
        try:
            headers = {"Content-Type": "application/json"}
            auth = self.data.get("n8n", {}).get("auth") or os.getenv("N8N_AUTH")
            if auth:
                headers["Authorization"] = auth
            r = requests.post(test_url, json={"ping": True}, headers=headers, timeout=10)
            ok = 200 <= r.status_code < 300
            return {"ok": ok, "detail": f"http {r.status_code}"}
        except requests.Timeout:
            return {"ok": False, "detail": "timeout"}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

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

    def health_cloudinary(self) -> dict:
        cfg = self.data.get("cloudinary", {})
        cloud_name = cfg.get("cloud_name")
        api_key = cfg.get("api_key")
        api_secret = cfg.get("api_secret")
        if not (cloud_name and api_key and api_secret):
            return {"ok": False, "detail": "not configured"}
        try:
            url = f"https://api.cloudinary.com/v1_1/{cloud_name}/ping"
            r = requests.get(url, timeout=10, auth=(api_key, api_secret))
            return {"ok": 200 <= r.status_code < 300, "detail": f"http {r.status_code}"}
        except Exception as e:
            return {"ok": False, "detail": f"{e}"}

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