from abc import ABC, abstractmethod
from urllib.parse import urlparse


class CommandHandler(ABC):
    def __init__(self, app, auth, apis, state, youtube, worksheet, n8n, youtube_channel_id: str):
        self.app = app
        self.auth = auth
        self.apis = apis
        self.state = state
        self.youtube = youtube
        self.worksheet = worksheet
        self.n8n = n8n
        self.youtube_channel_id = youtube_channel_id

    @abstractmethod
    def register(self):
        ...

    @staticmethod
    def _is_valid_url(u: str) -> bool:
        try:
            p = urlparse(u)
            return p.scheme in {"http", "https"} and bool(p.netloc)
        except Exception:
            return False