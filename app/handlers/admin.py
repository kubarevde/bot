import uuid
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from app.keyboards.main_menu import admin_menu_keyboard, cancel_keyboard
from app.services.sheets import SheetsClient
from app.states.workday import AdminAddShift, AdminCloseShift

router = Router()

WORK_TYPES = ["Поле", "Ремонт", "Закуп", "Дом", "Другое"]


def format_dt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y ") + str(dt.hour) + dt.strftime(":%M:%S")


def parse_dt(value: str) -> datetime:
    value = str(value).strip()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%d.%m.%Y %H:%M:%S")


def work_type_keyboard() -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=w)] for w in WORK_TYPES]
    rows.append([KeyboardButton(text="❌ Отмена")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def employee_keyboard(employees: list[dict]) -> ReplyKeyboardMarkup:
    rows = []
    for emp in employees:
        code = str(emp.get("employee_code", "")).strip()
        name = str(emp.get("employee_name", "")).strip()
        if code and name:
            rows.append([KeyboardButton(text=f"{name} [{code}]")])

    rows.append([KeyboardButton(text="❌ Отмена")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def human_dt(value: str) -> str:
    if not value:
        return "—"
    try:
        dt = parse_dt(value)
        return format_dt(dt)
    except Exception:
        return str(value)


def parse_employee_code_from_button(text: str) -> str:
    text = str(text).strip()
    if "[" in text and text.endswith("]"):
        return text.split("[")[-1].rstrip("]").strip()
    return ""


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

        lines.append(
            f"👤 <b>{employee_name}</b>\n"
            f"📍 Объект: {location}\n"
            f"🔧 Тип: {work_type}\n"
            f"🕐 Начало: {start_time}"
        )

    await message.answer(
        "👥 <b>Кто сейчас на смене:</b>\n\n" + "\n\n".join(lines),
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(F.text == "📝 Добавить смену за сотрудника")
async def admin_add_shift_begin(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if not sheets.is_admin(message.from_user.id):
        await message.answer("⛔ Команда доступна только администратору.")
        return

    employees = sheets.get_all_employees()
    if not employees:
        await message.answer("Список сотрудников пуст.", reply_markup=admin_menu_keyboard())
        return

    await state.clear()
    await state.set_state(AdminAddShift.employee_select)
    await message.answer(
        "Выбери сотрудника:",
        reply_markup=employee_keyboard(employees),
    )


@router.message(AdminAddShift.employee_select)
async def admin_add_shift_employee(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    employee_code = parse_employee_code_from_button(message.text)
    if not employee_code:
        await message.answer("Выбери сотрудника кнопкой из списка.")
        return

    employee = sheets.get_employee_by_code(employee_code)
    if not employee:
        await message.answer("Сотрудник не найден. Выбери сотрудника кнопкой из списка.")
        return

    if sheets.get_open_shift_by_employee_code(employee.get("employee_code", "")):
        await message.answer("У этого сотрудника уже есть открытая смена.")
        return

    await state.update_data(employee=employee)
    await state.set_state(AdminAddShift.start_time)
    await message.answer(
        "Введите время начала в формате YYYY-MM-DD HH:MM\n"
        "Пример: 2026-07-08 08:30",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminAddShift.start_time)
async def admin_add_shift_start_time(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    try:
        start_dt = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("Неверный формат. Используй YYYY-MM-DD HH:MM")
        return

    await state.update_data(start_time=format_dt(start_dt))
    await state.set_state(AdminAddShift.end_time)
    await message.answer(
        "Введите время окончания в формате YYYY-MM-DD HH:MM\n"
        "Пример: 2026-07-08 17:00",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminAddShift.end_time)
async def admin_add_shift_end_time(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    try:
        end_dt = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("Неверный формат. Используй YYYY-MM-DD HH:MM")
        return

    data = await state.get_data()
    start_dt = parse_dt(data["start_time"])

    if end_dt <= start_dt:
        await message.answer("Время окончания должно быть позже времени начала.")
        return

    await state.update_data(end_time=format_dt(end_dt))
    await state.set_state(AdminAddShift.location)
    await message.answer("Укажи объект / место работы:", reply_markup=cancel_keyboard())


@router.message(AdminAddShift.location)
async def admin_add_shift_location(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    await state.update_data(location=message.text.strip())
    await state.set_state(AdminAddShift.work_type)
    await message.answer("Выбери тип работы:", reply_markup=work_type_keyboard())


@router.message(AdminAddShift.work_type)
async def admin_add_shift_work_type(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    await state.update_data(work_type=message.text.strip())
    await state.set_state(AdminAddShift.equipment)
    await message.answer("Укажи технику/направление (или «нет»):", reply_markup=cancel_keyboard())


@router.message(AdminAddShift.equipment)
async def admin_add_shift_equipment(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    equipment = "" if message.text.strip().lower() in ("нет", "no", "-") else message.text.strip()
    await state.update_data(equipment=equipment)
    await state.set_state(AdminAddShift.description)
    await message.answer("Что сделал? Краткое описание работы:", reply_markup=cancel_keyboard())


@router.message(AdminAddShift.description)
async def admin_add_shift_description(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    await state.update_data(description=message.text.strip())
    await state.set_state(AdminAddShift.comment)
    await message.answer("Комментарий (или «нет»):", reply_markup=cancel_keyboard())


@router.message(AdminAddShift.comment)
async def admin_add_shift_comment(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    data = await state.get_data()
    employee = data["employee"]

    start_dt = parse_dt(data["start_time"])
    end_dt = parse_dt(data["end_time"])
    delta = end_dt - start_dt
    duration_raw = int(delta.total_seconds() // 60)
    duration_rounded = round((delta.total_seconds() / 3600) * 2) / 2

    comment_text = "" if message.text.strip().lower() in ("нет", "no", "-") else message.text.strip()
    admin_note = f"Добавлено админом @{message.from_user.username or message.from_user.id}"
    final_comment = admin_note if not comment_text else f"{admin_note}. {comment_text}"

    row = [
        str(uuid.uuid4())[:8],
        start_dt.date().isoformat(),
        employee.get("employee_code", ""),
        employee.get("employee_name", ""),
        str(employee.get("telegram_id", "")),
        data["start_time"],
        data["end_time"],
        data.get("work_type", ""),
        data.get("location", ""),
        data.get("equipment", ""),
        data.get("description", ""),
        final_comment,
        "closed",
        duration_raw,
        duration_rounded,
        "",
        "",
    ]

    try:
        sheets.append_work_log_row(row)
        await state.clear()
        await message.answer(
            f"✅ Смена за сотрудника добавлена.\n\n"
            f"👤 {employee.get('employee_name', '—')}\n"
            f"📍 {data.get('location', '—')}\n"
            f"🕐 {human_dt(data['start_time'])} → {human_dt(data['end_time'])}\n"
            f"⏱ {duration_rounded:.1f} ч",
            reply_markup=admin_menu_keyboard(),
        )
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Ошибка при записи смены: {e}",
            reply_markup=admin_menu_keyboard(),
        )


@router.message(F.text == "✅ Закрыть смену за сотрудника")
async def admin_close_shift_begin(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if not sheets.is_admin(message.from_user.id):
        await message.answer("⛔ Команда доступна только администратору.")
        return

    employees = sheets.get_all_employees()
    if not employees:
        await message.answer("Список сотрудников пуст.", reply_markup=admin_menu_keyboard())
        return

    await state.clear()
    await state.set_state(AdminCloseShift.employee_select)
    await message.answer(
        "Выбери сотрудника, чью открытую смену нужно закрыть:",
        reply_markup=employee_keyboard(employees),
    )


@router.message(AdminCloseShift.employee_select)
async def admin_close_shift_employee(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    employee_code = parse_employee_code_from_button(message.text)
    if not employee_code:
        await message.answer("Выбери сотрудника кнопкой из списка.")
        return

    employee = sheets.get_employee_by_code(employee_code)
    if not employee:
        await message.answer("Сотрудник не найден.")
        return

    row_index = sheets.get_open_shift_row_index_by_employee_code(employee.get("employee_code", ""))
    if not row_index:
        await message.answer("У сотрудника нет открытой смены.")
        return

    await state.update_data(employee=employee, row_index=row_index)
    await state.set_state(AdminCloseShift.end_time)
    await message.answer(
        "Введите время окончания в формате YYYY-MM-DD HH:MM",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminCloseShift.end_time)
async def admin_close_shift_end_time(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    try:
        end_dt = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("Неверный формат. Используй YYYY-MM-DD HH:MM")
        return

    data = await state.get_data()
    row_values = sheets.work_log_sheet().row_values(data["row_index"])
    start_time_str = row_values[5] if len(row_values) > 5 else ""

    try:
        start_dt = parse_dt(start_time_str)
    except ValueError:
        await message.answer("Не удалось прочитать время начала смены.")
        return

    if end_dt <= start_dt:
        await message.answer("Время окончания должно быть позже времени начала.")
        return

    await state.update_data(end_time=format_dt(end_dt))
    await state.set_state(AdminCloseShift.description)
    await message.answer("Что сделал? Краткое описание работы:", reply_markup=cancel_keyboard())


@router.message(AdminCloseShift.description)
async def admin_close_shift_description(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    await state.update_data(description=message.text.strip())
    await state.set_state(AdminCloseShift.comment)
    await message.answer("Комментарий (или «нет»):", reply_markup=cancel_keyboard())


@router.message(AdminCloseShift.comment)
async def admin_close_shift_comment(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    data = await state.get_data()
    row_values = sheets.work_log_sheet().row_values(data["row_index"])
    start_time_str = row_values[5] if len(row_values) > 5 else ""

    try:
        start_dt = parse_dt(start_time_str)
        end_dt = parse_dt(data["end_time"])
        delta = end_dt - start_dt
        duration_raw = int(delta.total_seconds() // 60)
        duration_rounded = round((delta.total_seconds() / 3600) * 2) / 2
    except ValueError:
        duration_raw = 0
        duration_rounded = 0.0

    comment_text = "" if message.text.strip().lower() in ("нет", "no", "-") else message.text.strip()
    admin_note = f"Закрыто админом @{message.from_user.username or message.from_user.id}"
    final_comment = admin_note if not comment_text else f"{admin_note}. {comment_text}"

    try:
        sheets.close_shift(
            row_index=data["row_index"],
            end_time=data["end_time"],
            description=data["description"],
            comment=final_comment,
            duration_raw=duration_raw,
            duration_rounded=duration_rounded,
        )
        await state.clear()
        await message.answer(
            f"✅ Смена сотрудника закрыта.\n\n"
            f"👤 {data['employee'].get('employee_name', '—')}\n"
            f"🕐 Конец: {human_dt(data['end_time'])}\n"
            f"⏱ Продолжительность: {duration_rounded:.1f} ч",
            reply_markup=admin_menu_keyboard(),
        )
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Ошибка при закрытии смены: {e}",
            reply_markup=admin_menu_keyboard(),
        )
