from pyrogram import filters
from commandHandler import CommandHandler


class startHandler(CommandHandler):
    def register(self):
        @self.app.on_message(filters.command("start"))
        async def start_handler(client, message):
            parts = message.text.split(maxsplit=1)
            already = self.auth.is_authorized(message.chat.id)

            if already:
                await message.reply("Вы уже авторизованы. Команды: /start_pipeline /stat /enqueue /autorun /autostop /set_description /api /api_check")
                return

            if len(parts) == 2:
                ok = self.auth.authorize(message.chat.id, parts[1])
                try:
                    await message.delete()
                except Exception:
                    pass
                if ok:
                    await message.reply("Авторизация успешна. Команды: /start_pipeline /stat /enqueue /autorun /autостоп /set_description /api /api_check")
                else:
                    await message.reply("Неверный пароль. Отправь: /start <пароль>")
                return

            await message.reply("Чтобы авторизоваться, отправь: /start <пароль>")