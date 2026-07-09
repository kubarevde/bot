import json
from datetime import datetime, date

import gspread
from google.oauth2.service_account import Credentials

from app.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def parse_sheet_dt(value: str) -> datetime | None:
    value = str(value).strip()
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value, "%d.%m.%Y %H:%M:%S")
        except ValueError:
            return None


class SheetsClient:
    def __init__(self, client: gspread.Client):
        self._client = client
        self._spreadsheet = client.open(settings.google_sheets_name)

    @classmethod
    def from_service_account(cls) -> "SheetsClient":
        if settings.google_creds_json:
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
        return self._spreadsheet.worksheet("employees")

    def work_log_sheet(self):
        return self._spreadsheet.worksheet("work_log")

    def append_work_log_row(self, row: list) -> None:
        self.work_log_sheet().append_row(row, value_input_option="RAW")

    def get_employee_by_telegram(self, telegram_id: int):
        rows = self.employees_sheet().get_all_records()
        for row in rows:
            if str(row.get("telegram_id", "")).strip() == str(telegram_id):
                return row
        return None

    def get_employee_by_code(self, employee_code: str):
        rows = self.employees_sheet().get_all_records()
        for row in rows:
            if str(row.get("employee_code", "")).strip() == str(employee_code).strip():
                return row
        return None

    def get_all_employees(self) -> list[dict]:
        return self.employees_sheet().get_all_records()

    def is_admin(self, telegram_id: int) -> bool:
        employee = self.get_employee_by_telegram(telegram_id)
        if not employee:
            return False
        return str(employee.get("role", "")).strip().lower() == "admin"

    def has_open_shift(self, telegram_id: int) -> bool:
        rows = self.work_log_sheet().get_all_records()
        for row in rows:
            if (
                str(row.get("telegram_id", "")).strip() == str(telegram_id)
                and str(row.get("status", "")).strip().lower() == "open"
            ):
                return True
        return False

    def get_open_shift(self, telegram_id: int):
        rows = self.work_log_sheet().get_all_records()
        for row in rows:
            if (
                str(row.get("telegram_id", "")).strip() == str(telegram_id)
                and str(row.get("status", "")).strip().lower() == "open"
            ):
                return row
        return None

    def get_open_shift_by_employee_code(self, employee_code: str):
        rows = self.work_log_sheet().get_all_records()
        for row in rows:
            if (
                str(row.get("employee_code", "")).strip() == str(employee_code).strip()
                and str(row.get("status", "")).strip().lower() == "open"
            ):
                return row
        return None

    def get_active_shifts(self) -> list[dict]:
        rows = self.work_log_sheet().get_all_records()
        return [row for row in rows if str(row.get("status", "")).strip().lower() == "open"]

    def get_shifts_for_date(self, target_date: date) -> list[dict]:
        rows = self.work_log_sheet().get_all_records()
        result = []

        for row in rows:
            row_date = str(row.get("date", "")).strip()
            start_time = str(row.get("start_time", "")).strip()

            if row_date:
                try:
                    if date.fromisoformat(row_date) == target_date:
                        result.append(row)
                        continue
                except ValueError:
                    pass

            dt = parse_sheet_dt(start_time)
            if dt and dt.date() == target_date:
                result.append(row)

        return result

    def get_user_shifts_for_date(self, telegram_id: int, target_date: date) -> list[dict]:
        rows = self.get_shifts_for_date(target_date)
        return [
            row for row in rows
            if str(row.get("telegram_id", "")).strip() == str(telegram_id)
        ]

    def get_open_shift_row_index(self, telegram_id: int):
        values = self.work_log_sheet().get_all_values()
        if not values:
            return None

        headers = values[0]
        try:
            telegram_id_idx = headers.index("telegram_id")
            status_idx = headers.index("status")
        except ValueError:
            return None

        for i, row in enumerate(values[1:], start=2):
            tg = row[telegram_id_idx] if len(row) > telegram_id_idx else ""
            st = row[status_idx] if len(row) > status_idx else ""
            if str(tg).strip() == str(telegram_id) and str(st).strip().lower() == "open":
                return i
        return None

    def get_open_shift_row_index_by_employee_code(self, employee_code: str):
        values = self.work_log_sheet().get_all_values()
        if not values:
            return None

        headers = values[0]
        try:
            employee_code_idx = headers.index("employee_code")
            status_idx = headers.index("status")
        except ValueError:
            return None

        for i, row in enumerate(values[1:], start=2):
            code = row[employee_code_idx] if len(row) > employee_code_idx else ""
            st = row[status_idx] if len(row) > status_idx else ""
            if (
                str(code).strip() == str(employee_code).strip()
                and str(st).strip().lower() == "open"
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
        sheet = self.work_log_sheet()
        sheet.update_cell(row_index, 7, end_time)
        sheet.update_cell(row_index, 11, description)
        sheet.update_cell(row_index, 12, comment)
        sheet.update_cell(row_index, 13, "closed")
        sheet.update_cell(row_index, 14, duration_raw)
        sheet.update_cell(row_index, 15, duration_rounded)
