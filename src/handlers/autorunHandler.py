import asyncio
from pyrogram import filters
from commandHandler import CommandHandler


class autorunHandler(CommandHandler):
    def register(self):
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

            self.state.set_autorun(enabled=True, minutes=mins, chat_id=message.chat.id)

            note_state = await self.n8n.trigger_autorun(message.chat.id, "start", mins)
            if note_state:
                await message.reply(f"{note_state}")

            note_start = await self.n8n.trigger_start(message.chat.id)
            if note_start:
                await message.reply(f"{note_start}")

            self.app.autorun_enabled = True if not hasattr(self.app, "autorun_enabled") else True
            self.app.autorun_minutes = mins if not hasattr(self.app, "autorun_minutes") else mins
            self.app.autorun_chat_id = message.chat.id if not hasattr(self.app, "autorun_chat_id") else message.chat.id

            if not hasattr(self.app, "autorun_task") or self.app.autorun_task is None or self.app.autorun_task.done():
                self.app.autorun_task = asyncio.create_task(self._autorun_loop(message.chat.id, mins))

    async def _autorun_loop(self, chat_id: int, minutes: int):
        await self.app.send_message(chat_id, f"Autorun включен. Интервал: {minutes} мин")
        while getattr(self.app, "autorun_enabled", False) and getattr(self.app, "autorun_chat_id", None) == chat_id:
            await asyncio.sleep(minutes * 60)
            if not getattr(self.app, "autorun_enabled", False) or getattr(self.app, "autorun_chat_id", None) != chat_id:
                break
            try:
                note = await self.n8n.trigger_start(chat_id)
                await self.app.send_message(chat_id, f"Запуск по расписанию.\n{note}")
                self.state.set_last_run_at(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
            except Exception as e:
                await self.app.send_message(chat_id, f"Ошибка в autorun: {e}")
        await self.app.send_message(chat_id, "Autorun остановлен")