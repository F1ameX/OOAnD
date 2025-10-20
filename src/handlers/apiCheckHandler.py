from pyrogram import filters
from commandHandler import CommandHandler


class apiCheckHandler(CommandHandler):
    def register(self):
        @self.app.on_message(filters.command("api_check"))
        async def api_check_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return
            text = self.apis.health_human(fallback_channel_id=self.youtube_channel_id)
            await message.reply(text)