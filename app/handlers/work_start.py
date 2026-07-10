import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from app.keyboards.main_menu import cancel_keyboard
from app.services.sheets import SheetsClient
from app.states.workday import StartWork
from app.utils.menu import menu_for_user

router = Router()
TZ = ZoneInfo("Asia/Bangkok")

MANUAL_INPUT_BUTTON = "✍️ Ввести вручную"


def format_dt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y ") + str(dt.hour) + dt.strftime(":%M:%S")


def options_keyboard(items: list[str], add_manual: bool = True) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=item)] for item in items]

    if add_manual:
        rows.append([KeyboardButton(text=MANUAL_INPUT_BUTTON)])

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
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    locations = sheets.get_locations()
    if not locations:
        await message.answer(
            "❌ Список объектов пуст. Заполните лист locations в Google Sheets.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    start_dt = datetime.now(TZ).replace(tzinfo=None)
    start_time_str = format_dt(start_dt)

    await state.update_data(
        employee=employee,
        start_time=start_time_str,
        locations=locations,
    )
    await state.set_state(StartWork.location)
    await message.answer(
        "📍 Где работаешь? Выбери объект или нажми «✍️ Ввести вручную»:",
        reply_markup=options_keyboard(locations, add_manual=True),
    )


@router.message(StartWork.location)
async def work_start_location(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=menu_for_user(sheets, message.from_user.id))
        return

    data = await state.get_data()
    locations = data.get("locations", [])

    if message.text == MANUAL_INPUT_BUTTON:
        await state.update_data(location_manual=True)
        await message.answer(
            "✍️ Введи объект или локацию вручную:",
            reply_markup=cancel_keyboard(),
        )
        return

    if locations and not data.get("location_manual") and message.text not in locations:
        await message.answer(
            "Выбери объект кнопкой или нажми «✍️ Ввести вручную».",
            reply_markup=options_keyboard(locations, add_manual=True),
        )
        return

    await state.update_data(location=message.text.strip(), location_manual=False)
    await state.set_state(StartWork.geo)
    await message.answer(
        "📍 Отправь геометку или нажми «Пропустить»:",
        reply_markup=geo_keyboard(),
    )


@router.message(StartWork.geo, F.location)
async def work_start_geo_location(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    work_types = sheets.get_work_types()
    if not work_types:
        await state.clear()
        await message.answer(
            "❌ Список типов работ пуст. Заполните лист work_types в Google Sheets.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    await state.update_data(
        latitude=f"{message.location.latitude:.6f}",
        longitude=f"{message.location.longitude:.6f}",
        work_types=work_types,
        work_type_manual=False,
    )
    await state.set_state(StartWork.work_type)
    await message.answer(
        "🔧 Выбери тип работы или нажми «✍️ Ввести вручную»:",
        reply_markup=options_keyboard(work_types, add_manual=True),
    )


@router.message(StartWork.geo, F.text == "⏭ Пропустить")
async def work_start_geo_skip(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    work_types = sheets.get_work_types()
    if not work_types:
        await state.clear()
        await message.answer(
            "❌ Список типов работ пуст. Заполните лист work_types в Google Sheets.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    await state.update_data(
        latitude="",
        longitude="",
        work_types=work_types,
        work_type_manual=False,
    )
    await state.set_state(StartWork.work_type)
    await message.answer(
        "🔧 Выбери тип работы или нажми «✍️ Ввести вручную»:",
        reply_markup=options_keyboard(work_types, add_manual=True),
    )


@router.message(StartWork.geo)
async def work_start_geo_invalid(message: Message) -> None:
    if message.text == "❌ Отмена":
        return
    await message.answer("Пожалуйста, отправь геометку кнопкой или нажми «⏭ Пропустить».")


@router.message(StartWork.work_type)
async def work_start_type(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=menu_for_user(sheets, message.from_user.id))
        return

    data = await state.get_data()
    work_types = data.get("work_types", [])

    if message.text == MANUAL_INPUT_BUTTON:
        await state.update_data(work_type_manual=True)
        await message.answer(
            "✍️ Введи тип работы вручную:",
            reply_markup=cancel_keyboard(),
        )
        return

    if work_types and not data.get("work_type_manual") and message.text not in work_types:
        await message.answer(
            "Выбери тип работы кнопкой или нажми «✍️ Ввести вручную».",
            reply_markup=options_keyboard(work_types, add_manual=True),
        )
        return

    equipment_items = sheets.get_equipment()
    if not equipment_items:
        await state.clear()
        await message.answer(
            "❌ Список техники пуст. Заполните лист equipment в Google Sheets.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    await state.update_data(
        work_type=message.text.strip(),
        work_type_manual=False,
        equipment_items=equipment_items,
        equipment_manual=False,
    )
    await state.set_state(StartWork.equipment)
    await message.answer(
        "🚜 Выбери технику/направление или нажми «✍️ Ввести вручную»:",
        reply_markup=options_keyboard(equipment_items, add_manual=True),
    )


@router.message(StartWork.equipment)
async def work_start_equipment(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=menu_for_user(sheets, message.from_user.id))
        return

    data = await state.get_data()
    equipment_items = data.get("equipment_items", [])

    if message.text == MANUAL_INPUT_BUTTON:
        await state.update_data(equipment_manual=True)
        await message.answer(
            "✍️ Введи технику или направление вручную:",
            reply_markup=cancel_keyboard(),
        )
        return

    if equipment_items and not data.get("equipment_manual") and message.text not in equipment_items:
        await message.answer(
            "Выбери технику кнопкой или нажми «✍️ Ввести вручную».",
            reply_markup=options_keyboard(equipment_items, add_manual=True),
        )
        return

    await state.update_data(equipment=message.text.strip(), equipment_manual=False)

    data = await state.get_data()
    employee = data["employee"]
    now = datetime.now(TZ).replace(tzinfo=None)

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
        "",
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
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Ошибка при записи в журнал: {e}",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
