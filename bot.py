import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.handlers import start, work_start, work_end, status
from app.services.sheets import SheetsClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main() -> None:
    bot = Bot(token=settings.bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
print("BOT_TOKEN exists:", bool(settings.bot_token))
print("GOOGLE_SHEETS_NAME:", settings.google_sheets_name)
print("GOOGLE_CREDS_PATH:", settings.google_creds_path)
print("GOOGLE_CREDS_JSON exists:", bool(settings.google_creds_json))
print("GOOGLE_CREDS_JSON preview:", str(settings.google_creds_json)[:80] if settings.google_creds_json else None)
    sheets_client = SheetsClient.from_service_account()

    dp["sheets"] = sheets_client

    dp.include_router(start.router)
    dp.include_router(work_start.router)
    dp.include_router(work_end.router)
    dp.include_router(status.router)

    logging.info("Bot started. Polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
