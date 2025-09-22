import os
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters

load_dotenv()


class MyBot:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("Токен бота не указан в .env файле.")

        self.app = Client(
            "processor",
            bot_token=self.bot_token
        )

        self.register_handlers()

    def register_handlers(self):
        @self.app.on_message(filters.command("start"))
        async def start_handler(client, message):
            pass # Что делаем на старте? 

        @self.app.on_message(filters.command("stat"))
        async def help_handler(client, message):
            pass # Какую стату тянем?

        @self.app.on_message(filters.command("enqueue"))
        async def ping_handler(client, message):
            pass # Интеграция с нодой

    def run(self):
        now = datetime.now()
        print(f'[{now}] Startin application ...')
        self.app.run()
        print(f'[{now}] Succesfully started')


if __name__ == "__main__":
    bot = MyBot()
    bot.run()