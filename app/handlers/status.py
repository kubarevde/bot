from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import Message

from app.services.sheets import SheetsClient
from app.utils.menu import menu_for_user

router = Router()
TZ = ZoneInfo("Asia/Bangkok")


@router.message(F.text == "📊 Мой статус")
async def my_status(message: Message, sheets: SheetsClient) -> None:
    open_shift = sheets.get_open_shift(message.from_user.id)
    if not open_shift:
        await message.answer(
            "ℹ️ Активной смены нет.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    start_time_raw = str(open_shift.get("start_time", "")).strip()
    try:
        start_dt = datetime.fromisoformat(start_time_raw)
        delta = datetime.now(TZ) - start_dt
        total_minutes = int(delta.total_seconds() // 60)
        if total_minutes < 0:
            total_minutes = 0
    except Exception:
        total_minutes = 0

    hours = total_minutes // 60
    minutes = total_minutes % 60

    geo_text = "есть" if open_shift.get("latitude") and open_shift.get("longitude") else "нет"

    await message.answer(
        f"📊 Текущая смена\n\n"
        f"📍 Объект: {open_shift.get('location', '—')}\n"
        f"🔧 Тип: {open_shift.get('work_type', '—')}\n"
        f"🚜 Техника: {open_shift.get('equipment', '—')}\n"
        f"🕐 Начало: {start_time_raw}\n"
        f"⏳ Прошло: {hours} ч. {minutes} мин.\n"
        f"📌 Геометка: {geo_text}",
        reply_markup=menu_for_user(sheets, message.from_user.id),
    )


@router.message(F.text == "📅 Сегодня")
async def today_info(message: Message, sheets: SheetsClient) -> None:
    await message.answer(
        "Раздел «Сегодня» пока в разработке.",
        reply_markup=menu_for_user(sheets, message.from_user.id),
    )
