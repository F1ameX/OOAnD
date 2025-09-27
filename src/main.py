import os
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters
from statsExtractor import statsExtractor

load_dotenv()


class MyBot:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN")
        self.api_id = os.getenv("API_ID")
        self.api_hash = os.getenv("API_HASH")
        self.youtube_key = os.getenv("YOUTUBE_API_KEY")
        self.youtube_channel_id = os.getenv("YOUTUBE_CHANNEL_ID")

        if not self.bot_token:
            raise ValueError("No token in .env file")

        self.app = Client(
            "processor",
            bot_token = self.bot_token,
            api_id = self.api_id,
            api_hash = self.api_hash
        )

        self.youtube = statsExtractor(api_key=self.youtube_key)
        self.register_handlers()

    def register_handlers(self):
        @self.app.on_message(filters.command("start"))
        async def start_handler(client, message):
            await message.reply("Started default queue pipeline.")

        @self.app.on_message(filters.command("stat"))
        async def stat_handler(client, message):
            result = self.youtube._get_channel_core_stats(self.youtube_channel_id)
            print(self.youtube._get_agent_core_stats(
                sa_json_path="src/account_stats.json",
                spreadsheet_url_or_key=os.getenv("TABLE_LINK"),
                worksheet_index=2,
                header_row=1
            ))
            await message.reply(result)

        @self.app.on_message(filters.command("enqueue"))
        async def enqueue_handler(client, message):
            await message.reply("Enqueued a new video for processing.")

    def run(self):
        now = datetime.now()
        print(f'[{now}] Starting application ...')
        self.app.run()
        print(f'[{now}] Succesfully started')


if __name__ == "__main__":
    bot = MyBot()
    bot.run()