from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message

from app.keyboards.main_menu import main_menu_keyboard
from app.services.sheets import SheetsClient

router = Router()


@router.message(F.text == "📊 Мой статус")
async def my_status(message: Message, sheets: SheetsClient) -> None:
    row_index = sheets.get_open_shift_row_index(message.from_user.id)
    if not row_index:
        await message.answer("ℹ️ Активной смены нет.", reply_markup=main_menu_keyboard())
        return

    sheet = sheets.work_log_sheet()
    row = sheet.row_values(row_index)
    start_time_str = row[5] if len(row) > 5 else ""
    location = row[8] if len(row) > 8 else "—"
    work_type = row[7] if len(row) > 7 else "—"

    elapsed = ""
    if start_time_str:
        try:
            start_dt = datetime.fromisoformat(start_time_str)
            delta = datetime.now() - start_dt
            minutes = int(delta.total_seconds() // 60)
            elapsed = f"{minutes // 60}ч {minutes % 60}м"
        except ValueError:
            pass

    await message.answer(
        f"🟢 У вас открытая смена:\n\n"
        f"📍 Объект: {location}\n"
        f"🔧 Тип: {work_type}\n"
        f"🕐 Начало: {start_time_str}\n"
        f"⏱ Прошло: {elapsed or '—'}",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "📅 Сегодня")
async def today_log(message: Message, sheets: SheetsClient) -> None:
    today = datetime.now().date().isoformat()
    values = sheets.work_log_sheet().get_all_records()
    rows = [
        r for r in values
        if str(r.get("telegram_id")) == str(message.from_user.id) and r.get("date") == today
    ]
    if not rows:
        await message.answer("📅 Сегодня записей нет.", reply_markup=main_menu_keyboard())
        return

    lines = []
    for r in rows:
        status_icon = "🟢" if r.get("status") == "open" else "✅"
        dur = r.get("duration_rounded_hours")
        dur_str = f" ({dur} ч)" if dur else ""
        lines.append(
            f"{status_icon} {r.get('start_time', '—')} → {r.get('end_time') or 'в работе'}{dur_str}\n"
            f"   📍 {r.get('location', '—')} | 🔧 {r.get('work_type', '—')}"
        )
    await message.answer(
        f"📅 Ваш журнал за сегодня ({today}):\n\n" + "\n\n".join(lines),
        reply_markup=main_menu_keyboard(),
    )
