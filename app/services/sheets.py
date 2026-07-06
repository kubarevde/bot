import json
import os
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
        self._sheet = client.open(settings.google_sheets_name).sheet1

    @classmethod
    def from_service_account(cls) -> "SheetsClient":
        # Приоритет: env-переменная GOOGLE_CREDS_JSON (для хостинга)
        if settings.google_creds_json:
            creds_dict = json.loads(settings.google_creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            # Локально: читаем из файла
            creds = Credentials.from_service_account_file(
                settings.google_creds_path, scopes=SCOPES
            )
        client = gspread.authorize(creds)
        return cls(client)

    def append_row(self, row: list) -> None:
        self._sheet.append_row(row)

    def get_all_records(self) -> list[dict]:
        return self._sheet.get_all_records()
