import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters

from youtubeExtractor import youtubeExtractor
from worksheetExtractor import worksheetExtractor
from authManager import authManager

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

        self.youtube = youtubeExtractor(api_key=self.youtube_key)
        self.worksheet = worksheetExtractor(
            file_location=self.file_location,
            spreadsheet_url=self.spreadsheet_url,
            worksheet_index=2,
        )

        self.autorun_enabled = False
        self.autorun_task = None
        self.autorun_minutes = 300

        self.register_handlers()

    async def run_pipeline(self, client, message):
        yt_stats = self.youtube._get_channel_core_stats(self.youtube_channel_id)
        sheet_stats = self.worksheet._get_agent_core_stats(header_row=1)
        sheet_text = sheet_stats.to_string(index=False)
        await message.reply(
            f"Пайплайн запущен\n\nYouTube:\n{yt_stats}\n\nSheets:\n{sheet_text}"
        )

    async def autorun_loop(self, client, message):
        await message.reply(f"Autorun включен. Интервал: {self.autorun_minutes} мин")
        while self.autorun_enabled:
            await asyncio.sleep(self.autorun_minutes * 60)
            if not self.autorun_enabled:
                break
            await self.run_pipeline(client, message)
        await message.reply("Autorun остановлен")

    def register_handlers(self):
        async def require_auth_or_reply(message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply(
                    "Доступ запрещён. Для авторизации отправь: <code>/start &lt;пароль&gt;</code>"
                )
                return False
            return True

        @self.app.on_message(filters.command("start"))
        async def start_handler(client, message):
            parts = message.text.split(maxsplit=1)
            already = self.auth.is_authorized(message.chat.id)

            if already:
                await message.reply(
                    "Вы уже авторизованы. Вам доступен весь функционал."
                )
                return

            if len(parts) == 2:
                ok = self.auth.authorize(message.chat.id, parts[1])
                try:
                    await message.delete()
                except Exception:
                    pass

                if ok:
                    await message.reply(
                        "Авторизация успешна."
                    )
                else:
                    await message.reply(
                        "Неверный пароль."
                    )
                return

            await message.reply(
                "Привет! Чтобы авторизоваться, отправь: <code>/start &lt;пароль&gt;</code>"
            )

        @self.app.on_message(filters.command("stat"))
        async def stat_handler(client, message):
            if not await require_auth_or_reply(message):
                return
            await self.run_pipeline(client, message)

        @self.app.on_message(filters.command("enqueue"))
        async def enqueue_handler(client, message):
            if not await require_auth_or_reply(message):
                return
            await message.reply("Enqueued a new video for processing.")

        @self.app.on_message(filters.command("autorun"))
        async def autorun_handler(client, message):
            if not await require_auth_or_reply(message):
                return

            args = message.text.split()
            mins = 300
            if len(args) > 1:
                try:
                    mins = int(args[1])
                except ValueError:
                    await message.reply("Некорректный аргумент. Пример: /autorun 120")
                    return

            if not (15 <= mins <= 1440):
                await message.reply("Допустимые значения минут: 15–1440")
                return

            self.autorun_minutes = mins
            self.autorun_enabled = True

            await self.run_pipeline(client, message)

            if self.autorun_task is None or self.autorun_task.done():
                self.autorun_task = asyncio.create_task(
                    self.autorun_loop(client, message)
                )

        @self.app.on_message(filters.command("autostop"))
        async def autostop_handler(client, message):
            if not await require_auth_or_reply(message):
                return

            if not self.autorun_enabled:
                await message.reply("Autorun уже выключен.")
                return

            self.autorun_enabled = False
            if self.autorun_task:
                self.autorun_task.cancel()
            await message.reply("Autorun выключен.")

    def run(self):
        now = datetime.now()
        print(f"[{now}] Starting application ...")
        self.app.run()
        print(f"[{now}] Exiting application ...")


if __name__ == "__main__":
    bot = MyBot()
    bot.run()