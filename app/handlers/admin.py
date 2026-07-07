from aiogram import F, Router
from aiogram.types import Message

from app.keyboards.main_menu import admin_menu_keyboard
from app.services.sheets import SheetsClient

router = Router()


def google_maps_link(latitude: str, longitude: str) -> str:
    return f"https://maps.google.com/?q={latitude},{longitude}"


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
        start_time = row.get("start_time", "—")
        latitude = str(row.get("latitude", "")).strip()
        longitude = str(row.get("longitude", "")).strip()

        if latitude and longitude:
            map_link = google_maps_link(latitude, longitude)
            geo_text = f'<a href="{map_link}">📍 Открыть карту</a>'
        else:
            geo_text = "📍 Геометка не указана"

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
