import os
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters
from youtubeExtractor import youtubeExtractor
from worksheetExtractor import worksheetExtractor

load_dotenv()


class MyBot:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN")
        self.api_id = os.getenv("API_ID")
        self.api_hash = os.getenv("API_HASH")
        self.youtube_key = os.getenv("YOUTUBE_API_KEY")
        self.youtube_channel_id = os.getenv("YOUTUBE_CHANNEL_ID")
        self.spreadsheet_url = os.getenv("TABLE_LINK")
        self.file_location = os.getenv("FILE_LOCATION")

        if not self.bot_token:
            raise ValueError("No token in .env file")

        self.app = Client(
            "processor",
            bot_token = self.bot_token,
            api_id = self.api_id,
            api_hash = self.api_hash
        )

        self.youtube = youtubeExtractor(api_key=self.youtube_key)
        self.worksheet = worksheetExtractor(file_location=self.file_location,
                                            spreadsheet_url=self.spreadsheet_url, 
                                            worksheet_index=2)
        self.register_handlers()

    def register_handlers(self):
        @self.app.on_message(filters.command("start"))
        async def start_handler(client, message):
            await message.reply("Started default queue pipeline.")

        
        @self.app.on_message(filters.command("stat"))
        async def stat_handler(client, message):
            yt_stats = self.youtube._get_channel_core_stats(self.youtube_channel_id)
            sheet_stats = self.worksheet._get_agent_core_stats(header_row=1)

            sheet_text = sheet_stats.to_string(index=False)
            await message.reply(f"📊 YouTube:\n{yt_stats}\n\n📑 Sheets:\n{sheet_text}")

        @self.app.on_message(filters.command("enqueue"))
        async def enqueue_handler(client, message):
            await message.reply("Enqueued a new video for processing.")

    def run(self):
        now = datetime.now()
        print(f'[{now}] Starting application ...')
        self.app.run()
        print(f'[{now}] Exiting application ...')


if __name__ == "__main__":
    bot = MyBot()
    bot.run()