import json
from pyrogram import filters
from commandHandler import CommandHandler


class apiAddHandler(CommandHandler):
    def register(self):
        @self.app.on_message(filters.command("api"))
        async def api_add_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                await message.reply("Пришли JSON после команды. Пример:\n/api {\"n8n\": {\"webhook_start\": \"https://...\"}}")
                return
            raw = args[1].strip()
            payload = json.loads(raw)
            result = self.apis.merge_and_save(payload)
            summary = {
                "updated": result.get("updated", []),
                "ignored": result.get("ignored", []),
                "errors": result.get("errors", []),
            }
            await message.reply(f"Готово. Результат:\n<pre>{json.dumps(summary, ensure_ascii=False, indent=2)}</pre>")