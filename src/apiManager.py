from __future__ import annotations
import json
import base64
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from googleapiclient.discovery import build
from gspread import service_account


def _ok(msg: str = "ok") -> Dict[str, Any]:
    return {"ok": True, "detail": msg}

def _err(msg: str) -> Dict[str, Any]:
    return {"ok": False, "detail": msg}


class apiManager:
    def __init__(self, secrets_path: str = "secrets.json"):
        self.path = Path(secrets_path)
        self.data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}
        else:
            self._save()

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def merge_update(self, payload: Dict[str, Any]) -> None:
        for k, v in (payload or {}).items():
            if isinstance(v, dict):
                self.data[k] = {**self.data.get(k, {}), **v}
            else:
                self.data[k] = v
        self._save()

    def redact_status(self) -> Dict[str, Any]:
        yt = self.data.get("youtube", {})
        sh = self.data.get("sheets", {})
        cl = self.data.get("cloudinary", {})
        sw = self.data.get("swiftia", {})
        ge = self.data.get("gemini", {})

        return {
            "youtube":   {"configured": bool(yt.get("api_key")), "channel_id": yt.get("channel_id")},
            "sheets":    {"configured": bool(sh.get("service_account_file") and sh.get("spreadsheet_url"))},
            "cloudinary":{"configured": bool(cl.get("cloud_name") and cl.get("api_key") and cl.get("api_secret"))},
            "swiftia":   {"configured": bool(sw.get("base_url"))},
            "gemini":    {"configured": bool(ge.get("api_key"))},
        }

    def health_all(self, fallback_channel_id: Optional[str] = None) -> Dict[str, Any]:
        results = {
            "youtube":   self.health_youtube(fallback_channel_id=fallback_channel_id),
            "sheets":    self.health_sheets(),
            "cloudinary":self.health_cloudinary(),
            "swiftia":   self.health_swiftia(),
            "gemini":    self.health_gemini(),
        }
        results["all_ok"] = all(v["ok"] for v in results.values())
        return results

    def health_youtube(self, *, fallback_channel_id: Optional[str] = None) -> Dict[str, Any]:
        yt = self.data.get("youtube", {})
        api_key = yt.get("api_key")
        channel_id = yt.get("channel_id") or fallback_channel_id
        if not api_key:
            return _err("no api_key")
        if not channel_id:
            return _err("no channel_id")

        try:
            yt_client = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
            resp = yt_client.channels().list(id=channel_id, part="id").execute()
            items = resp.get("items", [])
            if items:
                return _ok("reachable")
            return _err("channel not found")
        except Exception as e:
            return _err(f"youtube error: {e}")

    def health_sheets(self) -> Dict[str, Any]:
        sh = self.data.get("sheets", {})
        sa_file = sh.get("service_account_file")
        url = sh.get("spreadsheet_url")
        if not (sa_file and url):
            return _err("no service_account_file or spreadsheet_url")
        try:
            gc = service_account(filename=sa_file)
            book = gc.open_by_url(url)
            ws = book.sheet1
            _ = ws.get_all_values()
            return _ok("reachable")
        except Exception as e:
            return _err(f"sheets error: {e}")

    def health_cloudinary(self) -> Dict[str, Any]:
        cl = self.data.get("cloudinary", {})
        cloud_name = cl.get("cloud_name")
        api_key = cl.get("api_key")
        api_secret = cl.get("api_secret")
        if not (cloud_name and api_key and api_secret):
            return _err("no cloud_name/api_key/api_secret")
        try:
            url = f"https://api.cloudinary.com/v1_1/{cloud_name}/ping"
            basic = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
            r = requests.get(url, headers={"Authorization": f"Basic {basic}"}, timeout=10)
            if 200 <= r.status_code < 300:
                return _ok("reachable")
            return _err(f"http {r.status_code}: {r.text[:200]}")
        except Exception as e:
            return _err(f"cloudinary error: {e}")

    def health_swiftia(self) -> Dict[str, Any]:
        sw = self.data.get("swiftia", {})
        base_url = sw.get("base_url")
        auth = sw.get("auth")
        if not base_url:
            return _err("no base_url")
        try:
            headers = {"Authorization": auth} if auth else {}
            r = requests.get(base_url, headers=headers, timeout=10)
            if 200 <= r.status_code < 300:
                return _ok("reachable")
            return _err(f"http {r.status_code}: {r.text[:200]}")
        except Exception as e:
            return _err(f"swiftia error: {e}")

    def health_gemini(self) -> Dict[str, Any]:
        ge = self.data.get("gemini", {})
        api_key = ge.get("api_key")
        if not api_key:
            return _err("no api_key")
        try:
            r = requests.get(
                "https://generativelanguage.googleapis.com/v1/models",
                params={"key": api_key},
                timeout=10
            )
            if 200 <= r.status_code < 300:
                return _ok("reachable")
            return _err(f"http {r.status_code}: {r.text[:200]}")
        except Exception as e:
            return _err(f"gemini error: {e}")