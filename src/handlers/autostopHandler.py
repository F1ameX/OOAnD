from pyrogram import filters
from commandHandler import CommandHandler


class autostopHandler(CommandHandler):
    def register(self):
        @self.app.on_message(filters.command("autostop"))
        async def autostop_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return

            if not getattr(self.app, "autorun_enabled", False):
                await message.reply("Autorun уже выключен.")
                return

            self.app.autorun_enabled = False
            self.state.set_autorun(enabled=False, minutes=getattr(self.app, "autorun_minutes", 300), chat_id=getattr(self.app, "autorun_chat_id", message.chat.id))
            if getattr(self.app, "autorun_task", None):
                self.app.autorun_task.cancel()
            await message.reply("🛑 Autorun выключен.")