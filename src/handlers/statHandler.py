from pyrogram import filters
from commandHandler import CommandHandler


class statHandler(CommandHandler):
    def register(self):
        @self.app.on_message(filters.command("stat"))
        async def stat_handler(client, message):
            if not self.auth.is_authorized(message.chat.id):
                await message.reply("Доступ запрещён. Авторизуйся: /start <пароль>")
                return

            errors = []
            lines = []
            fmt = lambda n: f"{int(n):,}".replace(",", " ")

            yt_ok = False
            yt_block = []
            try:
                yt_raw = self.youtube._get_channel_core_stats(self.youtube_channel_id)
                if yt_raw is None:
                    raise RuntimeError("данные YouTube пустые")
                if isinstance(yt_raw, str):
                    import json as _json
                    yt = _json.loads(yt_raw)
                elif isinstance(yt_raw, dict):
                    yt = yt_raw
                else:
                    raise RuntimeError("неожиданный формат ответа YouTube")

                views = yt.get("views")
                subs = yt.get("subs")
                videos = yt.get("videos")
                last24 = yt.get("videos_last_24h")

                yt_block += [
                    "📺 YouTube:",
                    f"• Просмотры: {fmt(views) if views is not None else '—'}",
                    f"• Подписчики: {fmt(subs) if subs is not None else '—'}",
                    f"• Видео на канале: {fmt(videos) if videos is not None else '—'}",
                    f"• Видео за 24 часа: {fmt(last24) if last24 is not None else '—'}",
                ]
                yt_ok = True
            except Exception as e:
                errors.append(f"YouTube: {e}")

            gs_ok = False
            gs_block = []
            try:
                info = self.worksheet.get_info_metrics(sheet_name="stat")
                gs_block += [
                    "🤖 n8n Agent :",
                    f"• Видео обработано: {fmt(info.get('videos_processed', 0))}",
                    f"• Клипов обработано: {fmt(info.get('clips_processed', 0))}",
                    f"• Видео в очереди: {fmt(info.get('videos_in_queue', 0))}",
                    f"• Клипов в очереди: {fmt(info.get('clips_in_queue', 0))}",
                ]
                gs_ok = True
            except Exception as e:
                errors.append(f"Google Sheets: {e}")

            if yt_ok:
                lines += yt_block
            if gs_ok:
                if lines:
                    lines.append("")
                lines += gs_block

            if errors:
                if lines:
                    lines.append("")
                lines.append("⚠️ Предупреждения:")
                for err in errors:
                    lines.append(f"• {err}")

            if not yt_ok and not gs_ok:
                await message.reply("❌ Не удалось получить статистику ни из YouTube, ни из Google Sheets.\n" + "\n".join(f"• {e}" for e in errors))
                return

            await message.reply("\n".join(lines))