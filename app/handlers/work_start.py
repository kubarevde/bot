import uuid
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from app.keyboards.main_menu import cancel_keyboard, main_menu_keyboard
from app.services.sheets import SheetsClient
from app.states.workday import StartWork

router = Router()

WORK_TYPES = ["Поле", "Ремонт", "Закуп", "Дом", "Другое"]


def work_type_keyboard() -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=w)] for w in WORK_TYPES]
    rows.append([KeyboardButton(text="❌ Отмена")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def geo_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить геометку", request_location=True)],
            [KeyboardButton(text="⏭ Пропустить")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


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
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.update_data(
        employee=employee,
        start_time=datetime.now().isoformat(timespec="seconds"),
    )
    await state.set_state(StartWork.location)
    await message.answer(
        "📍 Где работаешь? Укажи объект или локацию:",
        reply_markup=cancel_keyboard(),
    )


@router.message(StartWork.location)
async def work_start_location(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return

    await state.update_data(location=message.text.strip())
    await state.set_state(StartWork.geo)
    await message.answer(
        "📍 Отправь геометку или нажми «Пропустить»:",
        reply_markup=geo_keyboard(),
    )


@router.message(StartWork.geo, F.location)
async def work_start_geo_location(message: Message, state: FSMContext) -> None:
    await state.update_data(
        latitude=f"{message.location.latitude:.6f}",
        longitude=f"{message.location.longitude:.6f}",
    )
    await state.set_state(StartWork.work_type)
    await message.answer(
        "🔧 Выбери тип работы:",
        reply_markup=work_type_keyboard(),
    )


@router.message(StartWork.geo, F.text == "⏭ Пропустить")
async def work_start_geo_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(latitude="", longitude="")
    await state.set_state(StartWork.work_type)
    await message.answer(
        "🔧 Выбери тип работы:",
        reply_markup=work_type_keyboard(),
    )


@router.message(StartWork.geo)
async def work_start_geo_invalid(message: Message) -> None:
    if message.text == "❌ Отмена":
        return
    await message.answer("Пожалуйста, отправь геометку кнопкой или нажми «⏭ Пропустить».")


@router.message(StartWork.work_type)
async def work_start_type(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return

    await state.update_data(work_type=message.text.strip())
    await state.set_state(StartWork.equipment)
    await message.answer(
        "🚜 Укажи технику или направление (или напиши «нет»):",
        reply_markup=cancel_keyboard(),
    )


@router.message(StartWork.equipment)
async def work_start_equipment(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return

    equipment = "" if message.text.strip().lower() in ("нет", "no", "-") else message.text.strip()
    await state.update_data(equipment=equipment)
    await state.set_state(StartWork.comment)
    await message.answer(
        "💬 Комментарий (или напиши «нет»):",
        reply_markup=cancel_keyboard(),
    )


@router.message(StartWork.comment)
async def work_start_comment(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return

    data = await state.get_data()
    employee = data["employee"]
    now = datetime.now()
    comment = "" if message.text.strip().lower() in ("нет", "no", "-") else message.text.strip()

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

        geo_info = "есть" if data.get("latitude") and data.get("longitude") else "нет"

        await message.answer(
            f"✅ Начало работы зафиксировано!\n\n"
            f"📍 Объект: {data.get('location')}\n"
            f"🔧 Тип: {data.get('work_type')}\n"
            f"🚜 Техника: {data.get('equipment') or '—'}\n"
            f"📌 Геометка: {geo_info}\n"
            f"🕐 Время: {data['start_time']}",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        await state.clear()
        await message.answer(
            "❌ Ошибка при записи в журнал. Попробуйте ещё раз или сообщите администратору.",
            reply_markup=main_menu_keyboard(),
        )
