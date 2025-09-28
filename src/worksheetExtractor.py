import pandas as pd
from typing import Optional
from gspread import service_account


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