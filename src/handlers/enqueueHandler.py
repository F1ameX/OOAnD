from pyrogram import filters
from commandHandler import CommandHandler


class enqueueHandler(CommandHandler):
    def register(self):
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