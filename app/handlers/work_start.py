import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from app.keyboards.main_menu import cancel_keyboard, location_keyboard
from app.services.sheets import SheetsClient
from app.states.workday import StartWork
from app.utils.menu import menu_for_user

router = Router()
TZ = ZoneInfo("Asia/Bangkok")

WORK_TYPES = ["Поле", "Ремонт", "Закуп", "Дом", "Другое"]


def work_type_keyboard() -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=w)] for w in WORK_TYPES]
    rows.append([KeyboardButton(text="❌ Отмена")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


@router.message(F.text == "🟢 Начал работу")
async def work_start_begin(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    employee = sheets.get_employee_by_telegram(message.from_user.id)
    if not employee:
        await message.answer("⛔ Вы не найдены в списке сотрудников.")
        return

    if sheets.has_open_shift(message.from_user.id):
        await message.answer(
            "⚠️ У вас уже есть открытая смена.\n"
            "Сначала завершите её, нажав «🔴 Закончил работу».",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    await state.update_data(
        employee=employee,
        start_time=datetime.now(TZ).isoformat(timespec="seconds"),
    )
    await state.set_state(StartWork.location)
    await message.answer(
        "📍 Где работаешь? Укажи объект или локацию вручную:",
        reply_markup=cancel_keyboard(),
    )


@router.message(StartWork.location)
async def work_start_location(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Отменено.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    await state.update_data(location=message.text)
    await state.set_state(StartWork.geo)
    await message.answer(
        "📌 Если хочешь, отправь геометку кнопкой ниже.\n"
        "Если не нужно — нажми «⏭ Пропустить».",
        reply_markup=location_keyboard(),
    )


@router.message(StartWork.geo, F.location)
async def work_start_geo_location(message: Message, state: FSMContext) -> None:
    await state.update_data(
        latitude=f"{message.location.latitude:.6f}",
        longitude=f"{message.location.longitude:.6f}",
    )
    await state.set_state(StartWork.work_type)
    await message.answer("🔧 Выбери тип работы:", reply_markup=work_type_keyboard())


@router.message(StartWork.geo, F.text == "⏭ Пропустить")
async def work_start_geo_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(latitude="", longitude="")
    await state.set_state(StartWork.work_type)
    await message.answer("🔧 Выбери тип работы:", reply_markup=work_type_keyboard())


@router.message(StartWork.geo, F.text == "❌ Отмена")
async def work_start_geo_cancel(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    await state.clear()
    await message.answer(
        "Отменено.",
        reply_markup=menu_for_user(sheets, message.from_user.id),
    )


@router.message(StartWork.geo)
async def work_start_geo_invalid(message: Message) -> None:
    await message.answer(
        "Пожалуйста, отправь геопозицию кнопкой ниже или нажми «⏭ Пропустить»."
    )


@router.message(StartWork.work_type)
async def work_start_type(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Отменено.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    await state.update_data(work_type=message.text)
    await state.set_state(StartWork.equipment)
    await message.answer(
        "🚜 Укажи технику или направление (или напиши «нет»):",
        reply_markup=cancel_keyboard(),
    )


@router.message(StartWork.equipment)
async def work_start_equipment(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Отменено.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    await state.update_data(equipment=message.text)
    await state.set_state(StartWork.comment)
    await message.answer(
        "💬 Комментарий (или напиши «нет»):",
        reply_markup=cancel_keyboard(),
    )


@router.message(StartWork.comment)
async def work_start_comment(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Отменено.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    data = await state.get_data()
    employee = data["employee"]
    now = datetime.now(TZ)
    comment = "" if message.text.lower() in ("нет", "no", "-") else message.text

    row = [
        str(uuid.uuid4())[:8],
        now.date().isoformat(),
        employee.get("employee_code", ""),
        employee.get("employee_name", ""),
        str(message.from_user.id),
        data["start_time"],
        "",
        data.get("work_type", ""),
        data.get("location", ""),
        data.get("equipment", ""),
        "",
        comment,
        "open",
        "",
        "",
        data.get("latitude", ""),
        data.get("longitude", ""),
    ]

    try:
        sheets.append_work_log_row(row)
        await state.clear()
        geo_text = (
            f"\n📌 Геометка: {data.get('latitude')}, {data.get('longitude')}"
            if data.get("latitude") and data.get("longitude")
            else "\n📌 Геометка: не указана"
        )
        await message.answer(
            f"✅ Начало работы зафиксировано!\n\n"
            f"📍 Объект: {data.get('location')}\n"
            f"🔧 Тип: {data.get('work_type')}\n"
            f"🚜 Техника: {data.get('equipment')}\n"
            f"🕐 Время: {data['start_time']}"
            f"{geo_text}",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Ошибка при записи в журнал: {e}",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
