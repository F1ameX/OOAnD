import json
import pandas as pd
from typing import Optional, Dict
from googleapiclient.discovery import build
from datetime import datetime, timezone, timedelta
from gspread import Client, Spreadsheet, Worksheet, service_account

class statsExtractor:
    def __init__(self, api_key : str = None) -> None:
        if api_key is None:
            raise ValueError('No YouTube API key provided')
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey = self.api_key, cache_discovery=False)

        self.view_count = None
        self.subscriber_count = None
        self.video_count = None
        self.videos_last_24h = None

    def _get_channel_core_stats(self, channel_id: str) -> Optional[Dict]:
        resp = self.youtube.channels().list(
            id = channel_id,
            part = "snippet,statistics"
        ).execute()

        items = resp.get("items", [])
        if not items:
            return None

        statistics = items[0].get("statistics", {})
        
        self.view_count = int(statistics.get("viewCount", 0))
        self.subscriber_count = int(statistics.get("subscriberCount", 0))
        self.video_count = int(statistics.get("videoCount", 0))
        self.videos_last_24h = self._count_videos_last_24h_search(channel_id)

        data = {
            'views' : self.view_count,
            'subs' : self.subscriber_count,
            'videos' : self.video_count,
            'videos_last_24h' : self.videos_last_24h
        }
        
        return json.dumps(data, ensure_ascii = False, indent = 4)

    def _count_videos_last_24h_search(self, channel_id: str) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24))
        published_after = cutoff.isoformat().replace("+00:00", "Z")

        total = 0
        page_token = None
        while True:
            resp = self.youtube.search().list(
                channelId=channel_id,
                part="id",
                type="video",
                order="date",
                publishedAfter=published_after,
                maxResults=50,
                pageToken=page_token
            ).execute()
            total += len(resp.get("items", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return total
    
    def _get_agent_core_stats(
        self,
        sa_json_path: str,
        spreadsheet_url_or_key: str,
        *,
        worksheet_name: Optional[str] = None,
        worksheet_index: Optional[int] = None,
        header_row: int = 1,
        drop_empty: bool = True
    ) -> pd.DataFrame:
        gc = service_account(filename=sa_json_path)

        if spreadsheet_url_or_key.startswith("http"):
            sh = gc.open_by_url(spreadsheet_url_or_key)
        else:
            sh = gc.open_by_key(spreadsheet_url_or_key)

        if worksheet_name is not None:
            ws = sh.worksheet(worksheet_name)
        elif worksheet_index is not None:
            ws = sh.get_worksheet(worksheet_index)
        else:
            ws = sh.get_worksheet(1)

        values = ws.get_all_values() 
        if not values:
            return pd.DataFrame()


        if header_row and header_row > 0:
            hdr_idx = header_row - 1
            if hdr_idx >= len(values):
                return pd.DataFrame()
            headers = values[hdr_idx]
            rows = values[hdr_idx + 1:]
            df = pd.DataFrame(rows, columns=headers)
        else:
            df = pd.DataFrame(values)

        if drop_empty:
            df = df.dropna(how="all").dropna(axis=1, how="all")

        return df