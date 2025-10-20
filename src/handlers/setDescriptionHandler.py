from datetime import datetime, timezone
from pyrogram import filters
from commandHandler import CommandHandler


class setDescriptionHandler(CommandHandler):
    def register(self):
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
            self.worksheet.append_description(
                description=description,
                video_url=video_url,
                chat_id=message.chat.id,
                timestamp_iso=ts,
                sheet_name="Descriptions",
            )
            await message.reply("Описание сохранено в Google Sheets")