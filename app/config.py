import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    bot_token: str = os.environ["BOT_TOKEN"]
    google_sheets_name: str = os.environ.get("GOOGLE_SHEETS_NAME", "worktime_bot")
    # Путь к файлу - для локальной разработки
    google_creds_path: str = os.environ.get("GOOGLE_CREDS_PATH", "credentials/service_account.json")
    # JSON строкой - для Bothost/продакшн (приоритет выше)
    google_creds_json: str | None = os.environ.get("GOOGLE_CREDS_JSON", None)


settings = Settings()
