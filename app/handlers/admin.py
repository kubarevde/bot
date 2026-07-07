from aiogram import F, Router
from aiogram.types import Message

from app.keyboards.main_menu import admin_menu_keyboard
from app.services.sheets import SheetsClient
from app.utils.datetime_fmt import human_dt

router = Router()


def normalize_coord(value) -> str:
    if value is None:
        return ""

    s = str(value).strip().replace(" ", "").replace(",", ".")
    if not s:
        return ""

    try:
        return f"{float(s):.6f}"
    except Exception:
        return ""


def google_maps_link(latitude, longitude) -> str:
    lat = normalize_coord(latitude)
    lon = normalize_coord(longitude)
    if not lat or not lon:
        return ""
    return f"https://maps.google.com/?q={lat},{lon}"


@router.message(F.text == "👥 Кто на смене")
async def who_is_working(message: Message, sheets: SheetsClient) -> None:
    if not sheets.is_admin(message.from_user.id):
        await message.answer("⛔ Команда доступна только администратору.")
        return

    active = sheets.get_active_shifts()
    if not active:
        await message.answer(
            "👥 Сейчас нет сотрудников с открытой сменой.",
            reply_markup=admin_menu_keyboard(),
        )
        return

    lines = []
    for row in active:
        employee_name = row.get("employee_name", "—")
        location = row.get("location", "—")
        work_type = row.get("work_type", "—")
        start_time = human_dt(row.get("start_time", ""))

        latitude = row.get("latitude", "")
        longitude = row.get("longitude", "")

        map_link = google_maps_link(latitude, longitude)

        if map_link:
            geo_text = f'<a href="{map_link}">📍 Открыть карту</a>'
        else:
            geo_text = "📍 Геометка не указана или записана некорректно"

        lines.append(
            f"👤 <b>{employee_name}</b>\n"
            f"📍 Объект: {location}\n"
            f"🔧 Тип: {work_type}\n"
            f"🕐 Начало: {start_time}\n"
            f"{geo_text}"
        )

    await message.answer(
        "👥 <b>Кто сейчас на смене:</b>\n\n" + "\n\n".join(lines),
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
