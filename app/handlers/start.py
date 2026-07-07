from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.services.sheets import SheetsClient
from app.utils.menu import menu_for_user

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, sheets: SheetsClient) -> None:
    employee = sheets.get_employee_by_telegram(message.from_user.id)
    if not employee:
        await message.answer(
            "⛔ У вас нет доступа к боту.\n"
            "Обратитесь к администратору, чтобы вас добавили в список сотрудников."
        )
        return

    await message.answer(
        f"👋 Привет, {employee.get('employee_name', message.from_user.first_name)}!\n\n"
        "Используйте кнопки ниже для учёта рабочего времени.",
        reply_markup=menu_for_user(sheets, message.from_user.id),
    )
