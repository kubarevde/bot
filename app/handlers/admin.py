from aiogram import F, Router
from aiogram.types import Message

from app.keyboards.main_menu import admin_menu_keyboard
from app.services.sheets import SheetsClient

router = Router()


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
        lines.append(
            f"👤 {row.get('employee_name', '—')}\n"
            f"📍 Объект: {row.get('location', '—')}\n"
            f"🔧 Тип: {row.get('work_type', '—')}\n"
            f"🕐 Начало: {row.get('start_time', '—')}"
        )

    await message.answer(
        "👥 Кто сейчас работает:\n\n" + "\n\n".join(lines),
        reply_markup=admin_menu_keyboard(),
    )
