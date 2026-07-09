from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import Message

from app.services.sheets import SheetsClient
from app.utils.menu import menu_for_user

router = Router()
TZ = ZoneInfo("Asia/Bangkok")


def parse_dt(value: str) -> datetime:
    value = str(value).strip()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%d.%m.%Y %H:%M:%S")


def human_dt(value: str) -> str:
    if not value:
        return "—"
    try:
        dt = parse_dt(value)
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        return str(value)


def build_geo_block(row: dict) -> str:
    lat = str(row.get("latitude", "")).strip()
    lon = str(row.get("longitude", "")).strip()

    if not lat or not lon:
        return "📌 Геометка: нет"

    maps_url = f"https://www.google.com/maps?q={lat},{lon}"
    return (
        f"📌 Геометка: есть\n"
        f"🧭 Координаты: {lat}, {lon}\n"
        f"🗺 Карта: {maps_url}"
    )


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
        start_dt = parse_dt(start_time_raw)
        now = datetime.now(TZ).replace(tzinfo=None)
        delta = now - start_dt
        total_minutes = int(delta.total_seconds() // 60)
        if total_minutes < 0:
            total_minutes = 0
    except Exception:
        total_minutes = 0

    hours = total_minutes // 60
    minutes = total_minutes % 60
    geo_block = build_geo_block(open_shift)

    await message.answer(
        f"📊 Текущая смена\n\n"
        f"📍 Объект: {open_shift.get('location', '—')}\n"
        f"🔧 Тип: {open_shift.get('work_type', '—')}\n"
        f"🚜 Техника: {open_shift.get('equipment', '—')}\n"
        f"🕐 Начало: {human_dt(start_time_raw)}\n"
        f"⏳ Прошло: {hours} ч. {minutes} мин.\n"
        f"{geo_block}",
        reply_markup=menu_for_user(sheets, message.from_user.id),
    )


@router.message(F.text == "📅 Сегодня")
async def today_info(message: Message, sheets: SheetsClient) -> None:
    now = datetime.now(TZ).replace(tzinfo=None)
    today = now.date()
    is_admin = sheets.is_admin(message.from_user.id)

    if is_admin:
        rows = sheets.get_shifts_for_date(today)
        title = f"📅 Все смены за сегодня ({today.strftime('%d.%m.%Y')})"
    else:
        rows = sheets.get_user_shifts_for_date(message.from_user.id, today)
        title = f"📅 Ваши смены за сегодня ({today.strftime('%d.%m.%Y')})"

    if not rows:
        await message.answer(
            "За сегодня смен не найдено.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    total_minutes = 0
    lines = []

    for row in rows:
        employee_name = row.get("employee_name", "—")
        work_type = row.get("work_type", "—")
        location = row.get("location", "—")
        equipment = row.get("equipment", "—")
        start_time = str(row.get("start_time", "")).strip()
        end_time = str(row.get("end_time", "")).strip()
        status = str(row.get("status", "")).strip().lower()
        duration_raw = row.get("duration_raw", 0)

        minutes = 0

        if status == "open":
            try:
                start_dt = parse_dt(start_time)
                minutes = max(0, int((now - start_dt).total_seconds() // 60))
            except Exception:
                minutes = 0
            status_text = "🟢 На смене"
            end_text = "сейчас"
        else:
            try:
                minutes = int(float(duration_raw)) if str(duration_raw).strip() else 0
            except (ValueError, TypeError):
                minutes = 0
            status_text = "✅ Закрыта"
            end_text = human_dt(end_time) if end_time else "—"

        total_minutes += minutes
        hours = minutes // 60
        mins = minutes % 60

        lat = str(row.get("latitude", "")).strip()
        lon = str(row.get("longitude", "")).strip()
        if lat and lon:
            geo_line = f"\n🗺 Карта: https://www.google.com/maps?q={lat},{lon}"
        else:
            geo_line = "\n📌 Геометка: нет"

        if is_admin:
            lines.append(
                f"👤 {employee_name}\n"
                f"📍 Объект: {location}\n"
                f"🔧 Тип: {work_type}\n"
                f"🚜 Техника: {equipment or '—'}\n"
                f"🕐 {human_dt(start_time)} → {end_text}\n"
                f"⏱ {hours} ч. {mins} мин.\n"
                f"{status_text}"
                f"{geo_line}"
            )
        else:
            lines.append(
                f"📍 Объект: {location}\n"
                f"🔧 Тип: {work_type}\n"
                f"🚜 Техника: {equipment or '—'}\n"
                f"🕐 {human_dt(start_time)} → {end_text}\n"
                f"⏱ {hours} ч. {mins} мин.\n"
                f"{status_text}"
                f"{geo_line}"
            )

    total_hours = total_minutes // 60
    total_mins = total_minutes % 60

    await message.answer(
        title + "\n\n" + "\n\n".join(lines) + f"\n\nИтого: {total_hours} ч. {total_mins} мин.",
        reply_markup=menu_for_user(sheets, message.from_user.id),
        parse_mode="HTML",
    )
