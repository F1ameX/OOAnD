import re
from typing import Optional, Dict, Any, List

import pandas as pd
from gspread import service_account, Worksheet
from gspread.exceptions import WorksheetNotFound


class worksheetExtractor:
    def __init__(
        self,
        file_location: str,
        spreadsheet_url: str,
        *,
        worksheet_index: Optional[int] = None
    ):
        self.spreadsheet_url = spreadsheet_url
        self.worksheet_index = worksheet_index
        self.file_location = file_location
        gc = service_account(filename=self.file_location)
        self.sh = gc.open_by_url(self.spreadsheet_url)
        if self.worksheet_index is not None:
            self.ws = self.sh.get_worksheet(self.worksheet_index)
        else:
            self.ws = self.sh.sheet1

    @staticmethod
    def _to_int_safe(v: Any, default: int = 0) -> int:
        if v is None:
            return default
        if isinstance(v, (int, float)):
            try:
                return int(v)
            except Exception:
                return default
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return default
            m = re.search(r"-?\d+", s.replace(" ", ""))
            if not m:
                return default
            try:
                return int(m.group(0))
            except Exception:
                return default
        return default

    @staticmethod
    def _first_non_empty_row(values: List[List[str]]) -> Optional[int]:
        for idx, row in enumerate(values):
            if any(str(cell).strip() for cell in row):
                return idx
        return None

    @staticmethod
    def _last_non_empty_row(values: List[List[str]]) -> Optional[int]:
        for idx in range(len(values) - 1, -1, -1):
            row = values[idx]
            if any(str(cell).strip() for cell in row):
                return idx
        return None

    def _get_worksheet_ci(self, name: str) -> Worksheet:
        target = (name or "").strip().lower()
        all_ws = self.sh.worksheets()
        for ws in all_ws:
            if (ws.title or "").strip().lower() == target:
                return ws
        titles = [ws.title for ws in all_ws]
        raise WorksheetNotFound(f"'{name}' not found. Available sheets: {titles}")

    def _get_headers_map(self, headers: List[str], row_values: List[str]) -> Dict[str, Any]:
        mp: Dict[str, Any] = {}
        for i, h in enumerate(headers):
            key = (h or "").strip()
            val = row_values[i] if i < len(row_values) else ""
            mp[key] = val
        return mp

    def _extract_exact_metrics(self, row_map: Dict[str, Any]) -> Dict[str, int]:
        required = {
            "videos proccessed": "videos_processed",
            "clips proccessed": "clips_processed",
            "videos in queue": "videos_in_queue",
            "clips in queue": "clips_in_queue",
        }
        out: Dict[str, int] = {
            "videos_processed": 0,
            "clips_processed": 0,
            "videos_in_queue": 0,
            "clips_in_queue": 0,
        }
        for src, dst in required.items():
            if src in row_map:
                out[dst] = self._to_int_safe(row_map[src], 0)
        return out

    def _get_active_sheet_values(self, ws: Worksheet) -> Dict[str, int]:
        values = ws.get_all_values()
        if not values:
            return {
                "videos_processed": 0,
                "clips_processed": 0,
                "videos_in_queue": 0,
                "clips_in_queue": 0,
            }
        hdr_idx = self._first_non_empty_row(values)
        if hdr_idx is None:
            return {
                "videos_processed": 0,
                "clips_processed": 0,
                "videos_in_queue": 0,
                "clips_in_queue": 0,
            }
        headers_raw = values[hdr_idx]
        last_idx = self._last_non_empty_row(values[hdr_idx + 1:])
        if last_idx is None:
            return {
                "videos_processed": 0,
                "clips_processed": 0,
                "videos_in_queue": 0,
                "clips_in_queue": 0,
            }
        row_values = values[hdr_idx + 1 + last_idx]
        row_map = self._get_headers_map(headers_raw, row_values)
        return self._extract_exact_metrics(row_map)

    def _get_sheet(self, sheet_name: str = "stst") -> Worksheet:
        return self._get_worksheet_ci(sheet_name)

    def _get_agent_core_stats(
        self,
        *,
        header_row: int = 1,
        drop_empty: bool = True
    ) -> pd.DataFrame:
        values = self.ws.get_all_values()
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

    def get_info_metrics(self, sheet_name: str = "stst") -> Dict[str, int]:
        try:
            ws = self._get_sheet(sheet_name)
        except WorksheetNotFound as e:
            raise RuntimeError(f"Лист '{sheet_name}' не найден: {e}")
        return self._get_active_sheet_values(ws)
