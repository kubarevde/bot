import json
import gspread
from google.oauth2.service_account import Credentials

from app.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    def __init__(self, client: gspread.Client):
        self._client = client
        self._spreadsheet = client.open(settings.google_sheets_name)
        self._employees_sheet = self._spreadsheet.sheet1
        try:
            self._work_log_sheet = self._spreadsheet.worksheet("work_log")
        except Exception:
            self._work_log_sheet = self._spreadsheet.get_worksheet(1)

    @classmethod
    def from_service_account(cls) -> "SheetsClient":
        if settings.google_creds_json and settings.google_creds_json.strip():
            creds_dict = json.loads(settings.google_creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file(
                settings.google_creds_path,
                scopes=SCOPES,
            )

        client = gspread.authorize(creds)
        return cls(client)

    def employees_sheet(self):
        return self._employees_sheet

    def work_log_sheet(self):
        return self._work_log_sheet

    def get_all_records(self) -> list[dict]:
        return self._employees_sheet.get_all_records()

    def append_row(self, row: list) -> None:
        self._employees_sheet.append_row(row)

    def append_work_log_row(self, row: list) -> None:
        self._work_log_sheet.append_row(row)

    def get_employee_by_telegram(self, telegram_id: int) -> dict | None:
        records = self._employees_sheet.get_all_records()
        for row in records:
            if str(row.get("telegram_id", "")).strip() == str(telegram_id):
                return row
        return None
        
    def is_admin(self, telegram_id: int) -> bool:
        employee = self.get_employee_by_telegram(telegram_id)
        return bool(employee and str(employee.get("role", "")).strip().lower() == "admin")
        
    def get_active_shifts(self) -> list[dict]:
        records = self._work_log_sheet.get_all_records()
        return [
            row for row in records
            if str(row.get("status", "")).strip().lower() == "open"
        ]
        
    def has_open_shift(self, telegram_id: int) -> bool:
        return self.get_open_shift_row_index(telegram_id) is not None

    def get_open_shift_row_index(self, telegram_id: int) -> int | None:
        records = self._work_log_sheet.get_all_records()
        for i, row in enumerate(records, start=2):
            if (
                str(row.get("telegram_id", "")).strip() == str(telegram_id)
                and str(row.get("status", "")).strip().lower() == "open"
            ):
                return i
        return None

    def close_shift(
        self,
        row_index: int,
        end_time: str,
        description: str,
        comment: str,
        duration_raw: int,
        duration_rounded: float,
    ) -> None:
        row_values = self._work_log_sheet.row_values(row_index)
        while len(row_values) < 15:
            row_values.append("")

        row_values[6] = end_time
        row_values[10] = description
        row_values[11] = comment
        row_values[12] = "closed"
        row_values[13] = str(duration_raw)
        row_values[14] = str(duration_rounded)

        self._work_log_sheet.update(f"A{row_index}:O{row_index}", [row_values])
