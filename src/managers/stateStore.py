from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, Dict, Any


class stateStore:
    def __init__(self, path: str = "runtime_state.json"):
        self.path = Path(path)
        self.data: Dict[str, Any] = {
            "autorun": {"enabled": False, "minutes": 300, "chat_id": None},
            "last_run_at": None,
        }
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                pass
        else:
            self.save()

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_autorun(self) -> Dict[str, Any]:
        return dict(self.data.get("autorun", {}))

    def set_autorun(self, *, enabled: bool, minutes: int, chat_id: Optional[int]) -> None:
        self.data["autorun"] = {"enabled": bool(enabled), "minutes": int(minutes), "chat_id": chat_id}
        self.save()

    def set_last_run_at(self, iso_ts: Optional[str]) -> None:
        self.data["last_run_at"] = iso_ts
        self.save()