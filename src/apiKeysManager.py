import json
import os


class apiManager:
    def __init__(self, secrets_path: str = "secrets.json"):
        self.secrets_path = secrets_path
        self.data = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.secrets_path):
                with open(self.secrets_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            else:
                self.data = {}
        except Exception:
            self.data = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.secrets_path), exist_ok=True) if os.path.dirname(self.secrets_path) else None
        with open(self.secrets_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def health_all(self, fallback_channel_id: str = "") -> dict:
        res = {"all_ok": True}

        n8n = self.data.get("n8n", {})
        n8n_ok = bool(n8n.get("webhook_start")) and bool(n8n.get("webhook_enqueue")) and bool(n8n.get("webhook_autorun"))
        res["n8n"] = {
            "webhook_start": n8n.get("webhook_start"),
            "webhook_enqueue": n8n.get("webhook_enqueue"),
            "webhook_autorun": n8n.get("webhook_autorun"),
            "ok": n8n_ok,
        }
        res["all_ok"] = res["all_ok"] and n8n_ok

        yt = self.data.get("youtube", {})
        yt_ok = bool(os.getenv("YOUTUBE_API_KEY") or yt.get("api_key")) and bool(os.getenv("YOUTUBE_CHANNEL_ID") or fallback_channel_id or yt.get("channel_id"))
        res["youtube"] = {
            "api_key_present": bool(os.getenv("YOUTUBE_API_KEY") or yt.get("api_key")),
            "channel_id_checked": os.getenv("YOUTUBE_CHANNEL_ID") or yt.get("channel_id") or fallback_channel_id,
            "ok": yt_ok,
        }
        res["all_ok"] = res["all_ok"] and yt_ok

        sh = self.data.get("sheets", {})
        sh_ok = bool(os.getenv("FILE_LOCATION") or sh.get("service_account_file")) and bool(os.getenv("TABLE_LINK") or sh.get("spreadsheet_url"))
        res["sheets"] = {
            "service_account_file": os.getenv("FILE_LOCATION") or sh.get("service_account_file"),
            "spreadsheet_url_present": bool(os.getenv("TABLE_LINK") or sh.get("spreadsheet_url")),
            "ok": sh_ok,
        }
        res["all_ok"] = res["all_ok"] and sh_ok

        res["cloudinary"] = {"ok": True}
        res["swiftia"] = {"ok": True}
        res["gemini"] = {"ok": True}

        return res

    def merge_and_save(self, payload: dict) -> dict:
        updated = []
        ignored = []
        errors = []

        if not isinstance(payload, dict):
            return {"updated": [], "ignored": [], "errors": ["payload is not dict"]}

        allowed_sections = {"n8n", "youtube", "sheets", "cloudinary", "swiftia", "gemini"}
        for section, content in payload.items():
            if section not in allowed_sections:
                ignored.append(section)
                continue
            if not isinstance(content, dict):
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