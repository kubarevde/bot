import calendar
import uuid
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    CallbackQuery,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.main_menu import admin_menu_keyboard, cancel_keyboard
from app.services.sheets import SheetsClient
from app.states.workday import AdminAddShift, AdminCloseShift, AdminBroadcast

router = Router()
TZ = ZoneInfo("Asia/Bangkok")
MANUAL_INPUT_BUTTON = "✍️ Ввести вручную"


class DatePickCallback(CallbackData, prefix="dp"):
    action: str
    year: int
    month: int
    day: int
    target: str


class TimePickCallback(CallbackData, prefix="tp"):
    hour: int
    minute: int
    target: str


class QuickDateCallback(CallbackData, prefix="qd"):
    action: str
    target: str


def format_dt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y ") + str(dt.hour) + dt.strftime(":%M:%S")


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
        return format_dt(dt)
    except Exception:
        return str(value)


def combine_date_time(d: date, hour: int, minute: int) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute, 0)


def resolve_quick_date(action: str) -> date:
    today = date.today()
    if action == "today":
        return today
    if action == "yesterday":
        return today - timedelta(days=1)
    if action == "tomorrow":
        return today + timedelta(days=1)
    return today


def build_geo_lines(row: dict) -> str:
    lat = str(row.get("latitude", "")).strip()
    lon = str(row.get("longitude", "")).strip()

    if not lat or not lon:
        return "📌 Геометка: нет"

    return (
        f"📌 Геометка: есть\n"
        f"🧭 Координаты: {lat}, {lon}\n"
        f"🗺 Карта: https://www.google.com/maps?q={lat},{lon}"
    )


def employee_keyboard(employees: list[dict]) -> ReplyKeyboardMarkup:
    rows = []
    for emp in employees:
        code = str(emp.get("employee_code", "")).strip()
        name = str(emp.get("employee_name", "")).strip()
        if code and name:
            rows.append([KeyboardButton(text=f"{name} [{code}]")])

    rows.append([KeyboardButton(text="❌ Отмена")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def options_keyboard(items: list[str], add_manual: bool = True) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=item)] for item in items]

    if add_manual:
        rows.append([KeyboardButton(text=MANUAL_INPUT_BUTTON)])

    rows.append([KeyboardButton(text="❌ Отмена")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def comment_choice_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Нет")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def parse_employee_code_from_button(text: str) -> str:
    text = str(text).strip()
    if "[" in text and text.endswith("]"):
        return text.split("[")[-1].rstrip("]").strip()
    return ""


def quick_date_keyboard(target: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Сегодня", callback_data=QuickDateCallback(action="today", target=target))
    builder.button(text="Вчера", callback_data=QuickDateCallback(action="yesterday", target=target))
    builder.button(text="Завтра", callback_data=QuickDateCallback(action="tomorrow", target=target))
    builder.button(text="📅 Другая дата", callback_data=QuickDateCallback(action="calendar", target=target))
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def month_calendar_keyboard(year: int, month: int, target: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(
        text=f"{calendar.month_name[month]} {year}",
        callback_data=DatePickCallback(action="ignore", year=year, month=month, day=0, target=target),
    )

    for wd in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]:
        builder.button(
            text=wd,
            callback_data=DatePickCallback(action="ignore", year=year, month=month, day=0, target=target),
        )

    for week in calendar.monthcalendar(year, month):
        for day_num in week:
            if day_num == 0:
                builder.button(
                    text=" ",
                    callback_data=DatePickCallback(action="ignore", year=year, month=month, day=0, target=target),
                )
            else:
                builder.button(
                    text=str(day_num),
                    callback_data=DatePickCallback(
                        action="select",
                        year=year,
                        month=month,
                        day=day_num,
                        target=target,
                    ),
                )

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    builder.button(
        text="◀️",
        callback_data=DatePickCallback(action="prev", year=prev_year, month=prev_month, day=1, target=target),
    )
    builder.button(
        text="Сегодня",
        callback_data=DatePickCallback(
            action="current",
            year=date.today().year,
            month=date.today().month,
            day=date.today().day,
            target=target,
        ),
    )
    builder.button(
        text="▶️",
        callback_data=DatePickCallback(action="next", year=next_year, month=next_month, day=1, target=target),
    )

    builder.adjust(1, 7, 7, 7, 7, 7, 7, 1, 3)
    return builder.as_markup()


def time_keyboard(target: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for hour in range(0, 24):
        builder.button(
            text=f"{hour:02d}:00",
            callback_data=TimePickCallback(hour=hour, minute=0, target=target),
        )
        builder.button(
            text=f"{hour:02d}:30",
            callback_data=TimePickCallback(hour=hour, minute=30, target=target),
        )
    builder.adjust(4)
    return builder.as_markup()


@router.message(
    F.text == "❌ Отмена",
    (
        AdminAddShift.employee_select,
        AdminAddShift.start_date,
        AdminAddShift.start_time,
        AdminAddShift.end_date,
        AdminAddShift.end_time,
        AdminAddShift.location,
        AdminAddShift.work_type,
        AdminAddShift.equipment,
        AdminAddShift.description,
        AdminAddShift.comment,
        AdminCloseShift.employee_select,
        AdminCloseShift.end_date,
        AdminCloseShift.end_time,
        AdminCloseShift.description,
        AdminCloseShift.comment,
        AdminBroadcast.target_select,
        AdminBroadcast.message_text,
    ),
)
async def admin_calendar_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_menu_keyboard())


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
        equipment = row.get("equipment", "—")
        start_time = human_dt(row.get("start_time", ""))
        geo_lines = build_geo_lines(row)

        lines.append(
            f"👤 {employee_name}\n"
            f"📍 Объект: {location}\n"
            f"🔧 Тип: {work_type}\n"
            f"🚜 Техника: {equipment or '—'}\n"
            f"🕐 Начало: {start_time}\n"
            f"{geo_lines}"
        )

    await message.answer(
        "👥 Кто сейчас на смене:\n\n" + "\n\n".join(lines),
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(F.text == "📣 Написать всем")
async def broadcast_all_begin(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if not sheets.is_admin(message.from_user.id):
        await message.answer("⛔ Команда доступна только администратору.")
        return

    await state.clear()
    await state.update_data(broadcast_target="all")
    await state.set_state(AdminBroadcast.message_text)
    await message.answer(
        "Введите сообщение для всех сотрудников, у кого подключен бот:",
        reply_markup=cancel_keyboard(),
    )


@router.message(F.text == "📣 Написать кто на смене")
async def broadcast_active_begin(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if not sheets.is_admin(message.from_user.id):
        await message.answer("⛔ Команда доступна только администратору.")
        return

    await state.clear()
    await state.update_data(broadcast_target="active")
    await state.set_state(AdminBroadcast.message_text)
    await message.answer(
        "Введите сообщение для сотрудников, которые сейчас на смене:",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminBroadcast.message_text)
async def broadcast_send(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    data = await state.get_data()
    target = data.get("broadcast_target")
    text = message.text.strip()

    if not text:
        await message.answer("Сообщение пустое. Введи текст или нажми «❌ Отмена».")
        return

    if target == "all":
        recipient_ids = sheets.get_all_employee_telegram_ids()
        title = "📢 Сообщение от администратора"
    else:
        recipient_ids = sheets.get_active_shift_telegram_ids()
        title = "📢 Сообщение от администратора для сотрудников на смене"

    if not recipient_ids:
        await state.clear()
        await message.answer(
            "❌ Не найдено получателей для рассылки.",
            reply_markup=admin_menu_keyboard(),
        )
        return

    sent_count = 0
    fail_count = 0

    for tg_id in recipient_ids:
        try:
            await message.bot.send_message(
                tg_id,
                f"{title}\n\n{text}",
            )
            sent_count += 1
        except Exception:
            fail_count += 1

    await state.clear()
    await message.answer(
        f"✅ Рассылка завершена.\n\n"
        f"Отправлено: {sent_count}\n"
        f"Не доставлено: {fail_count}",
        reply_markup=admin_menu_keyboard(),
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
    await message.answer("Выбери сотрудника:", reply_markup=employee_keyboard(employees))


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
    await state.set_state(AdminAddShift.start_date)
    await message.answer("Выбери дату начала:", reply_markup=quick_date_keyboard("add_start"))


@router.callback_query(QuickDateCallback.filter(F.target == "add_start"))
async def admin_add_start_quick_date(
    callback: CallbackQuery,
    callback_data: QuickDateCallback,
    state: FSMContext,
) -> None:
    if callback_data.action == "calendar":
        today = date.today()
        await callback.message.edit_text(
            "Выбери дату начала:",
            reply_markup=month_calendar_keyboard(today.year, today.month, "add_start"),
        )
    else:
        selected_date = resolve_quick_date(callback_data.action)
        await state.update_data(start_date_value=selected_date.isoformat())
        await state.set_state(AdminAddShift.start_time)
        await callback.message.edit_text(
            f"Дата начала: {selected_date.strftime('%d.%m.%Y')}\nВыбери время начала:",
            reply_markup=time_keyboard("add_start"),
        )
    await callback.answer()


@router.callback_query(DatePickCallback.filter(F.target == "add_start"))
async def admin_add_start_calendar(
    callback: CallbackQuery,
    callback_data: DatePickCallback,
    state: FSMContext,
) -> None:
    if callback_data.action == "ignore":
        await callback.answer()
        return

    if callback_data.action in ("prev", "next", "current"):
        await callback.message.edit_reply_markup(
            reply_markup=month_calendar_keyboard(callback_data.year, callback_data.month, "add_start")
        )
        await callback.answer()
        return

    if callback_data.action == "select":
        selected_date = date(callback_data.year, callback_data.month, callback_data.day)
        await state.update_data(start_date_value=selected_date.isoformat())
        await state.set_state(AdminAddShift.start_time)
        await callback.message.edit_text(
            f"Дата начала: {selected_date.strftime('%d.%m.%Y')}\nВыбери время начала:",
            reply_markup=time_keyboard("add_start"),
        )
        await callback.answer()
        return


@router.callback_query(TimePickCallback.filter(F.target == "add_start"))
async def admin_add_start_time(
    callback: CallbackQuery,
    callback_data: TimePickCallback,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    start_date_value = date.fromisoformat(data["start_date_value"])
    start_dt = combine_date_time(start_date_value, callback_data.hour, callback_data.minute)

    await state.update_data(start_time=format_dt(start_dt))
    await state.set_state(AdminAddShift.end_date)
    await callback.message.edit_text(
        f"Начало: {format_dt(start_dt)}\n\nВыбери дату окончания:",
        reply_markup=quick_date_keyboard("add_end"),
    )
    await callback.answer()


@router.callback_query(QuickDateCallback.filter(F.target == "add_end"))
async def admin_add_end_quick_date(
    callback: CallbackQuery,
    callback_data: QuickDateCallback,
    state: FSMContext,
) -> None:
    if callback_data.action == "calendar":
        today = date.today()
        await callback.message.edit_text(
            "Выбери дату окончания:",
            reply_markup=month_calendar_keyboard(today.year, today.month, "add_end"),
        )
    else:
        selected_date = resolve_quick_date(callback_data.action)
        await state.update_data(end_date_value=selected_date.isoformat())
        await state.set_state(AdminAddShift.end_time)
        await callback.message.edit_text(
            f"Дата окончания: {selected_date.strftime('%d.%m.%Y')}\nВыбери время окончания:",
            reply_markup=time_keyboard("add_end"),
        )
    await callback.answer()


@router.callback_query(DatePickCallback.filter(F.target == "add_end"))
async def admin_add_end_calendar(
    callback: CallbackQuery,
    callback_data: DatePickCallback,
    state: FSMContext,
) -> None:
    if callback_data.action == "ignore":
        await callback.answer()
        return

    if callback_data.action in ("prev", "next", "current"):
        await callback.message.edit_reply_markup(
            reply_markup=month_calendar_keyboard(callback_data.year, callback_data.month, "add_end")
        )
        await callback.answer()
        return

    if callback_data.action == "select":
        selected_date = date(callback_data.year, callback_data.month, callback_data.day)
        await state.update_data(end_date_value=selected_date.isoformat())
        await state.set_state(AdminAddShift.end_time)
        await callback.message.edit_text(
            f"Дата окончания: {selected_date.strftime('%d.%m.%Y')}\nВыбери время окончания:",
            reply_markup=time_keyboard("add_end"),
        )
        await callback.answer()
        return


@router.callback_query(TimePickCallback.filter(F.target == "add_end"))
async def admin_add_end_time(
    callback: CallbackQuery,
    callback_data: TimePickCallback,
    state: FSMContext,
    sheets: SheetsClient,
) -> None:
    data = await state.get_data()
    start_dt = parse_dt(data["start_time"])
    end_date_value = date.fromisoformat(data["end_date_value"])
    end_dt = combine_date_time(end_date_value, callback_data.hour, callback_data.minute)

    if end_dt <= start_dt:
        await callback.answer("Окончание должно быть позже начала", show_alert=True)
        return

    locations = sheets.get_locations()
    if not locations:
        await state.clear()
        await callback.message.answer(
            "❌ Список объектов пуст. Заполните лист locations.",
            reply_markup=admin_menu_keyboard(),
        )
        await callback.answer()
        return

    await state.update_data(
        end_time=format_dt(end_dt),
        locations=locations,
        location_manual=False,
    )
    await state.set_state(AdminAddShift.location)
    await callback.message.edit_text(
        f"Окончание: {format_dt(end_dt)}\n\nВыбери объект или нажми «✍️ Ввести вручную»:"
    )
    await callback.message.answer(
        "📍 Выбери объект или нажми «✍️ Ввести вручную»:",
        reply_markup=options_keyboard(locations, add_manual=True),
    )
    await callback.answer()


@router.message(AdminAddShift.location)
async def admin_add_shift_location(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    data = await state.get_data()
    locations = data.get("locations", [])

    if message.text == MANUAL_INPUT_BUTTON:
        await state.update_data(location_manual=True)
        await message.answer("✍️ Введи объект или локацию вручную:", reply_markup=cancel_keyboard())
        return

    if locations and not data.get("location_manual") and message.text not in locations:
        await message.answer(
            "Выбери объект кнопкой или нажми «✍️ Ввести вручную».",
            reply_markup=options_keyboard(locations, add_manual=True),
        )
        return

    work_types = sheets.get_work_types()
    if not work_types:
        await state.clear()
        await message.answer("❌ Список типов работ пуст. Заполните лист work_types.", reply_markup=admin_menu_keyboard())
        return

    await state.update_data(
        location=message.text.strip(),
        location_manual=False,
        work_types=work_types,
        work_type_manual=False,
    )
    await state.set_state(AdminAddShift.work_type)
    await message.answer(
        "🔧 Выбери тип работы или нажми «✍️ Ввести вручную»:",
        reply_markup=options_keyboard(work_types, add_manual=True),
    )


@router.message(AdminAddShift.work_type)
async def admin_add_shift_work_type(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    data = await state.get_data()
    work_types = data.get("work_types", [])

    if message.text == MANUAL_INPUT_BUTTON:
        await state.update_data(work_type_manual=True)
        await message.answer("✍️ Введи тип работы вручную:", reply_markup=cancel_keyboard())
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
        await message.answer("❌ Список техники пуст. Заполните лист equipment.", reply_markup=admin_menu_keyboard())
        return

    await state.update_data(
        work_type=message.text.strip(),
        work_type_manual=False,
        equipment_items=equipment_items,
        equipment_manual=False,
    )
    await state.set_state(AdminAddShift.equipment)
    await message.answer(
        "🚜 Выбери технику/направление или нажми «✍️ Ввести вручную»:",
        reply_markup=options_keyboard(equipment_items, add_manual=True),
    )


@router.message(AdminAddShift.equipment)
async def admin_add_shift_equipment(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    data = await state.get_data()
    equipment_items = data.get("equipment_items", [])

    if message.text == MANUAL_INPUT_BUTTON:
        await state.update_data(equipment_manual=True)
        await message.answer("✍️ Введи технику или направление вручную:", reply_markup=cancel_keyboard())
        return

    if equipment_items and not data.get("equipment_manual") and message.text not in equipment_items:
        await message.answer(
            "Выбери технику кнопкой или нажми «✍️ Ввести вручную».",
            reply_markup=options_keyboard(equipment_items, add_manual=True),
        )
        return

    await state.update_data(equipment=message.text.strip(), equipment_manual=False)
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
            f"🔧 {data.get('work_type', '—')}\n"
            f"🚜 {data.get('equipment', '—') or '—'}\n"
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
    await state.set_state(AdminCloseShift.end_date)
    await message.answer("Выбери дату окончания:", reply_markup=quick_date_keyboard("close_end"))


@router.callback_query(QuickDateCallback.filter(F.target == "close_end"))
async def admin_close_end_quick_date(
    callback: CallbackQuery,
    callback_data: QuickDateCallback,
    state: FSMContext,
) -> None:
    if callback_data.action == "calendar":
        today = date.today()
        await callback.message.edit_text(
            "Выбери дату окончания:",
            reply_markup=month_calendar_keyboard(today.year, today.month, "close_end"),
        )
    else:
        selected_date = resolve_quick_date(callback_data.action)
        await state.update_data(end_date_value=selected_date.isoformat())
        await state.set_state(AdminCloseShift.end_time)
        await callback.message.edit_text(
            f"Дата окончания: {selected_date.strftime('%d.%m.%Y')}\nВыбери время окончания:",
            reply_markup=time_keyboard("close_end"),
        )
    await callback.answer()


@router.callback_query(DatePickCallback.filter(F.target == "close_end"))
async def admin_close_end_calendar(
    callback: CallbackQuery,
    callback_data: DatePickCallback,
    state: FSMContext,
) -> None:
    if callback_data.action == "ignore":
        await callback.answer()
        return

    if callback_data.action in ("prev", "next", "current"):
        await callback.message.edit_reply_markup(
            reply_markup=month_calendar_keyboard(callback_data.year, callback_data.month, "close_end")
        )
        await callback.answer()
        return

    if callback_data.action == "select":
        selected_date = date(callback_data.year, callback_data.month, callback_data.day)
        await state.update_data(end_date_value=selected_date.isoformat())
        await state.set_state(AdminCloseShift.end_time)
        await callback.message.edit_text(
            f"Дата окончания: {selected_date.strftime('%d.%m.%Y')}\nВыбери время окончания:",
            reply_markup=time_keyboard("close_end"),
        )
        await callback.answer()
        return


@router.callback_query(TimePickCallback.filter(F.target == "close_end"))
async def admin_close_end_time(
    callback: CallbackQuery,
    callback_data: TimePickCallback,
    state: FSMContext,
    sheets: SheetsClient,
) -> None:
    data = await state.get_data()
    end_date_value = date.fromisoformat(data["end_date_value"])
    end_dt = combine_date_time(end_date_value, callback_data.hour, callback_data.minute)

    row_values = sheets.work_log_sheet().row_values(data["row_index"])
    start_time_str = row_values[5] if len(row_values) > 5 else ""

    try:
        start_dt = parse_dt(start_time_str)
    except ValueError:
        await callback.answer("Не удалось прочитать время начала", show_alert=True)
        return

    if end_dt <= start_dt:
        await callback.answer("Окончание должно быть позже начала", show_alert=True)
        return

    await state.update_data(end_time=format_dt(end_dt))
    await state.set_state(AdminCloseShift.description)
    await callback.message.edit_text(
        f"Окончание: {format_dt(end_dt)}\n\nЧто сделал? Краткое описание работы:"
    )
    await callback.message.answer("Что сделал? Краткое описание работы:", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(AdminCloseShift.description)
async def admin_close_shift_description(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    await state.update_data(description=message.text.strip())
    await state.set_state(AdminCloseShift.comment)
    await message.answer("Комментарий к завершению:", reply_markup=comment_choice_keyboard())


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

    comment_text = "" if message.text.strip() == "Нет" else message.text.strip()
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
