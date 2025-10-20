from pyrogram import filters
from commandHandler import CommandHandler


class startPipelineHandler(CommandHandler):
    def register(self):
        @self.app.on_message(filters.command("start_pipeline"))
        async def start_pipeline_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return
            note = await self.n8n.trigger_start(message.chat.id)
            await message.reply(f"{note}")