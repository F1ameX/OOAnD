import os
import json
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse

from dotenv import load_dotenv
from pyrogram import Client, filters, idle

from youtubeExtractor import youtubeExtractor
from worksheetExtractor import worksheetExtractor
from authManager import authManager
from apiKeysManager import apiManager
from stateStore import stateStore
from n8nManager import n8nManager

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

        ar = self.state.get_autorun()
        self.autorun_enabled = bool(ar.get("enabled", False))
        self.autorun_minutes = int(ar.get("minutes", 300))
        self.autorun_chat_id = ar.get("chat_id")
        self.autorun_task = None

        self.register_handlers()

    async def run_pipeline(self, client, message):
        yt_stats = self.youtube._get_channel_core_stats(self.youtube_channel_id)
        sheet_stats = self.worksheet._get_agent_core_stats(header_row=1)
        sheet_text = sheet_stats.to_string(index=False)

        await message.reply(f"Пайплайн: проверка метрик\n\n📊 YouTube:\n{yt_stats}\n\n📑 Sheets:\n{sheet_text}")

        note = await self.n8n.trigger_start(message.chat.id)
        await message.reply(note)

        self.state.set_last_run_at(datetime.now(timezone.utc).isoformat())

    async def autorun_loop(self, chat_id: int):
        await self.app.send_message(chat_id, f"Autorun включен. Интервал: {self.autorun_minutes} мин")
        while self.autorun_enabled and self.autorun_chat_id == chat_id:
            await asyncio.sleep(self.autorun_minutes * 60)
            if not self.autorun_enabled or self.autorun_chat_id != chat_id:
                break
            try:
                note = await self.n8n.trigger_start(chat_id)
                await self.app.send_message(chat_id, f"Запуск по расписанию.\n{note}")
                self.state.set_last_run_at(datetime.now(timezone.utc).isoformat())
            except Exception as e:
                await self.app.send_message(chat_id, f"Ошибка в autorun: {e}")
        await self.app.send_message(chat_id, "Autorun остановлен")

    def register_handlers(self):
        async def require_auth_or_reply(message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Для авторизации отправь: <code>/start &lt;пароль&gt;</code>")
                return False
            return True

        @self.app.on_message(filters.command("start"))
        async def start_handler(client, message):
            parts = message.text.split(maxsplit=1)
            already = self.auth.is_authorized(message.chat.id)

            if already:
                await message.reply("Вы уже авторизованы.")
                return

            if len(parts) == 2:
                ok = self.auth.authorize(message.chat.id, parts[1])
                try:
                    await message.delete()
                except Exception:
                    pass
                if ok:
                    await message.reply("Авторизация успешна.")
                else:
                    await message.reply("Неверный пароль. Отправь: <code>/start &lt;пароль&gt;</code>")
                return

            await message.reply("Привет! Чтобы авторизоваться, отправь: <code>/start &lt;пароль&gt;</code>")

        @self.app.on_message(filters.command("start_pipeline"))
        async def start_pipeline_handler(client, message):
            if not await require_auth_or_reply(message):
                return
            note = await self.n8n.trigger_start(message.chat.id)
            await message.reply(f"{note}")

        @self.app.on_message(filters.command("stat"))
        async def stat_handler(client, message):
            if not await require_auth_or_reply(message):
                return
            yt_stats = self.youtube._get_channel_core_stats(self.youtube_channel_id)
            sheet_stats = self.worksheet._get_agent_core_stats(header_row=1)
            sheet_text = sheet_stats.to_string(index=False)
            await message.reply(f"📊 YouTube:\n{yt_stats}\n\n📑 Sheets:\n{sheet_text}")

        @self.app.on_message(filters.command("enqueue"))
        async def enqueue_handler(client, message):
            if not await require_auth_or_reply(message):
                return
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                await message.reply("Используй: <code>/enqueue &lt;url&gt;</code>")
                return

            url_to_enqueue = args[1].strip()
            if not self._is_valid_url(url_to_enqueue):
                await message.reply("❌ Некорректный URL. Нужен http(s)://...")
                return

            note = await self.n8n.trigger_enqueue(message.chat.id, url_to_enqueue)
            await message.reply(note)
        # 
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
            self.autorun_chat_id = message.chat.id
            self.state.set_autorun(enabled=True, minutes=mins, chat_id=message.chat.id)

            await message.reply(f"Autorun включен (каждые {mins} мин).")
            _ = await self.n8n.trigger_autorun(message.chat.id, "start", mins)
            note = await self.n8n.trigger_start(message.chat.id)
            await message.reply(note)

            if self.autorun_task is None or self.autorun_task.done():
                self.autorun_task = asyncio.create_task(self.autorun_loop(message.chat.id))

        @self.app.on_message(filters.command("autostop"))
        async def autostop_handler(client, message):
            if not await require_auth_or_reply(message):
                return

            if not self.autorun_enabled:
                await message.reply("Autorun уже выключен.")
                return

            self.autorun_enabled = False
            self.state.set_autorun(enabled=False, minutes=self.autorun_minutes, chat_id=self.autorun_chat_id)
            if self.autorun_task:
                self.autorun_task.cancel()

            _ = await self.n8n.trigger_autorun(message.chat.id, "stop")

            await message.reply("🛑 Autorun выключен.")

        @self.app.on_message(filters.command("api_check"))
        async def api_check_handler(client, message):
            if not await require_auth_or_reply(message):
                return
            results = self.apis.health_all(fallback_channel_id=self.youtube_channel_id)
            msg = "✅ Все API работают." if results.get("all_ok") else "❌ Есть проблемы с API."
            await message.reply(f"{msg}\n<pre>{json.dumps(results, ensure_ascii=False, indent=2)}</pre>")

    @staticmethod
    def _is_valid_url(u: str) -> bool:
        try:
            p = urlparse(u)
            return p.scheme in {"http", "https"} and bool(p.netloc)
        except Exception:
            return False

    async def _bootstrap(self):
        ar = self.state.get_autorun()
        if ar.get("enabled") and ar.get("chat_id"):
            self.autorun_enabled = True
            self.autorun_minutes = int(ar.get("minutes", 300))
            self.autorun_chat_id = int(ar.get("chat_id"))
            self.autorun_task = asyncio.create_task(self.autorun_loop(self.autorun_chat_id))

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