import json
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse
from pyrogram import filters


class CommandHandler:
    def __init__(self, app, auth, apis, state, youtube, worksheet, n8n, youtube_channel_id: str):
        self.app = app
        self.auth = auth
        self.apis = apis
        self.state = state
        self.youtube = youtube
        self.worksheet = worksheet
        self.n8n = n8n
        self.youtube_channel_id = youtube_channel_id

        self.autorun_enabled = False
        self.autorun_minutes = 300
        self.autorun_chat_id = None
        self.autorun_task = None

    def register(self):
        @self.app.on_message(filters.command("start"))
        async def start_handler(client, message):
            parts = message.text.split(maxsplit=1)
            already = self.auth.is_authorized(message.chat.id)

            if already:
                await message.reply("Вы уже авторизованы. Команды: /start_pipeline /stat /enqueue /autorun /autostop /set_description /api_add /api_check")
                return

            if len(parts) == 2:
                ok = self.auth.authorize(message.chat.id, parts[1])
                try:
                    await message.delete()
                except Exception:
                    pass
                if ok:
                    await message.reply("Авторизация успешна. Команды: /start_pipeline /stat /enqueue /autorun /autостop /set_description /api_add /api_check")
                else:
                    await message.reply("Неверный пароль. Отправь: /start <пароль>")
                return

            await message.reply("Чтобы авторизоваться, отправь: /start <пароль>")

        @self.app.on_message(filters.command("start_pipeline"))
        async def start_pipeline_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return
            note = await self.n8n.trigger_start(message.chat.id)
            await message.reply(f"{note}")

        @self.app.on_message(filters.command("stat"))
        async def stat_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return
            yt_stats = self.youtube._get_channel_core_stats(self.youtube_channel_id)
            sheet_stats = self.worksheet._get_agent_core_stats(header_row=1)
            sheet_text = sheet_stats.to_string(index=False)
            await message.reply(f"📊 YouTube:\n{yt_stats}\n\n📑 Sheets:\n{sheet_text}")

        @self.app.on_message(filters.command("enqueue"))
        async def enqueue_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                await message.reply("Используй: /enqueue <url>")
                return
            url_to_enqueue = args[1].strip()
            if not self._is_valid_url(url_to_enqueue):
                await message.reply("Некорректный URL. Нужен http(s)://...")
                return
            note = await self.n8n.trigger_enqueue(message.chat.id, url_to_enqueue)
            await message.reply(note)

        @self.app.on_message(filters.command("autorun"))
        async def autorun_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
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

            note_state = await self.n8n.trigger_autorun(message.chat.id, "start", mins)
            await message.reply(f"{note_state}")

            note_start = await self.n8n.trigger_start(message.chat.id)
            await message.reply(f"{note_start}")

            if self.autorun_task is None or self.autorun_task.done():
                self.autorun_task = asyncio.create_task(self.autorun_loop(message.chat.id))

        @self.app.on_message(filters.command("autostop"))
        async def autostop_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return
            if not self.autorun_enabled:
                await message.reply("Autorun уже выключен.")
                return

            self.autorun_enabled = False
            self.state.set_autorun(enabled=False, minutes=self.autorun_minutes, chat_id=self.autorun_chat_id)
            if self.autorun_task:
                self.autorun_task.cancel()

            note = await self.n8n.trigger_autorun(message.chat.id, "stop")
            await message.reply(f"{note}")

        @self.app.on_message(filters.command("api_check"))
        async def api_check_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return
            results = self.apis.health_all(fallback_channel_id=self.youtube_channel_id)
            msg = "✅ Все API работают." if results.get("all_ok") else "❌ Есть проблемы с API."
            await message.reply(f"{msg}\n<pre>{json.dumps(results, ensure_ascii=False, indent=2)}</pre>")

        @self.app.on_message(filters.command("set_description"))
        async def set_description_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                await message.reply("Используй: /set_description <текст> или /set_description <url> | <текст>")
                return

            payload = args[1].strip()
            video_url = None
            description = payload
            if "|" in payload:
                p1, p2 = payload.split("|", 1)
                if self._is_valid_url(p1.strip()):
                    video_url = p1.strip()
                    description = p2.strip()

            ts = datetime.now(timezone.utc).isoformat()
            try:
                self.worksheet.append_description(
                    description=description,
                    video_url=video_url,
                    chat_id=message.chat.id,
                    timestamp_iso=ts,
                    sheet_name="Descriptions",
                )
                await message.reply("Описание сохранено в Google Sheets")
            except Exception as e:
                await message.reply(f"Ошибка записи в Google Sheets: {e}")

        @self.app.on_message(filters.command("api_add"))
        async def api_add_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                await message.reply("Пришли JSON после команды. Пример:\n/api_add {\"n8n\": {\"webhook_start\": \"https://...\"}}")
                return
            raw = args[1].strip()
            try:
                payload = json.loads(raw)
                result = self.apis.merge_and_save(payload)
                summary = {
                    "updated": result.get("updated", []),
                    "ignored": result.get("ignored", []),
                    "errors": result.get("errors", []),
                }
                await message.reply(f"Готово. Результат:\n<pre>{json.dumps(summary, ensure_ascii=False, indent=2)}</pre>")
            except json.JSONDecodeError:
                await message.reply("Невалидный JSON")
            except Exception as e:
                await message.reply(f"Ошибка сохранения: {e}")

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

    async def bootstrap_autorun(self):
        ar = self.state.get_autorun()
        if ar.get("enabled") and ar.get("chat_id"):
            self.autorun_enabled = True
            self.autorun_minutes = int(ar.get("minutes", 300))
            self.autorun_chat_id = int(ar.get("chat_id"))
            if self.autorun_task is None or self.autorun_task.done():
                self.autorun_task = asyncio.create_task(self.autorun_loop(self.autorun_chat_id))

    @staticmethod
    def _is_valid_url(u: str) -> bool:
        try:
            p = urlparse(u)
            return p.scheme in {"http", "https"} and bool(p.netloc)
        except Exception:
            return False