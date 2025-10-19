import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, idle

from youtubeExtractor import youtubeExtractor
from worksheetExtractor import worksheetExtractor
from authManager import authManager
from apiKeysManager import apiManager
from stateStore import stateStore
from n8nManager import n8nManager
from commandHandler import CommandHandler

load_dotenv()


class MyBot:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN")
        self.api_id = os.getenv("API_ID")
        self.api_hash = os.getenv("API_HASH")
        self.youtube_key = os.getenv("YOUTUBE_API_KEY")
        self.youtube_channel_id = os.getenv("YOUTUBE_CHANNEL_ID")
        self.spreadsheet_url = os.getenv("TABLE_LINK")
        self.file_location = os.getenv("FILE_LOCATION")

        if not self.bot_token:
            raise ValueError("No token in .env file")

        self.app = Client(
            "processor",
            bot_token=self.bot_token,
            api_id=self.api_id,
            api_hash=self.api_hash,
        )

        self.auth = authManager(
            state_path=os.getenv("STATE_PATH", "state.json"),
            passphrase=os.getenv("AUTH_PASSPHRASE", ""),
        )
        self.apis = apiManager(secrets_path=os.getenv("SECRETS_PATH", "secrets.json"))
        self.state = stateStore(path=os.getenv("RUNTIME_STATE_PATH", "runtime_state.json"))

        self.youtube = youtubeExtractor(api_key=self.youtube_key)
        self.worksheet = worksheetExtractor(
            file_location=self.file_location,
            spreadsheet_url=self.spreadsheet_url,
            worksheet_index=2,
        )
        self.n8n = n8nManager()

        self.handlers = CommandHandler(
            app=self.app,
            auth=self.auth,
            apis=self.apis,
            state=self.state,
            youtube=self.youtube,
            worksheet=self.worksheet,
            n8n=self.n8n,
            youtube_channel_id=self.youtube_channel_id,
        )
        self.handlers.register()

    async def _bootstrap(self):
        await self.handlers.bootstrap_autorun()

    def run(self):
        now = datetime.now()
        print(f"[{now}] Starting application ...")

        async def runner():
            await self.app.start()
            await self._bootstrap()
            await idle()
            await self.app.stop()

        self.app.run(runner())
        print(f"[{now}] Exiting application ...")


if __name__ == "__main__":
    bot = MyBot()
    bot.run()