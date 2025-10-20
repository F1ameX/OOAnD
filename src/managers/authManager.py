from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Iterable, Set


class authManager:
    def __init__(
        self,
        state_path: str = "state.json",
        passphrase: str | None = None,
        initial_whitelist: Iterable[int] | None = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.passphrase = passphrase or os.getenv("AUTH_PASSPHRASE", "").strip()
        self._authorized: Set[int] = set(initial_whitelist or [])
        self._load()

    def is_authorized(self, chat_id: int) -> bool:
        return int(chat_id) in self._authorized

    def authorize(self, chat_id: int, passphrase: str) -> bool:
        if not self._check_pass(passphrase):
            return False
        self._authorized.add(int(chat_id))
        self._save()
        return True

    def revoke(self, chat_id: int) -> None:
        self._authorized.discard(int(chat_id))
        self._save()

    def list_authorized(self) -> list[int]:
        return sorted(self._authorized)

    def _load(self) -> None:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                self._authorized = set(int(x) for x in data.get("authorized_chats", []))
            except Exception:
                self._authorized = set()
        else:
            self._save()

    def _save(self) -> None:
        data = {"authorized_chats": sorted(self._authorized)}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _check_pass(self, passphrase: str) -> bool:
        expected = (self.passphrase or "").strip()
        got = (passphrase or "").strip()
        return bool(expected) and got == expected