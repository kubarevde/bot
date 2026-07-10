from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from app.keyboards.main_menu import cancel_keyboard
from app.services.sheets import SheetsClient
from app.states.workday import EndWork
from app.utils.menu import menu_for_user

router = Router()
TZ = ZoneInfo("Asia/Bangkok")


def format_dt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y ") + str(dt.hour) + dt.strftime(":%M:%S")


def parse_dt(value: str) -> datetime:
    value = str(value).strip()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%d.%m.%Y %H:%M:%S")


def round_hours_from_minutes(minutes: int) -> float:
    hours = minutes / 60
    return round(hours * 2) / 2


def end_comment_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Нет")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.message(F.text == "🔴 Закончил работу")
async def work_end_begin(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    row_index = sheets.get_open_shift_row_index(message.from_user.id)
    if not row_index:
        await message.answer(
            "⚠️ У вас нет открытой смены.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    await state.set_state(EndWork.description)
    await message.answer(
        "📝 Что было сделано за смену?",
        reply_markup=cancel_keyboard(),
    )


@router.message(EndWork.description)
async def work_end_description(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Отменено.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    await state.update_data(description=message.text.strip())
    await state.set_state(EndWork.comment)
    await message.answer(
        "💬 Комментарий к завершению:",
        reply_markup=end_comment_keyboard(),
    )


@router.message(EndWork.comment)
async def work_end_comment(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Отменено.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    data = await state.get_data()
    row_index = sheets.get_open_shift_row_index(message.from_user.id)

    if not row_index:
        await state.clear()
        await message.answer(
            "❌ Не удалось найти открытую смену.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    open_shift = sheets.get_open_shift(message.from_user.id)
    if not open_shift:
        await state.clear()
        await message.answer(
            "❌ Не удалось прочитать открытую смену.",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    end_dt = datetime.now(TZ).replace(tzinfo=None)
    end_time_str = format_dt(end_dt)
    start_time_raw = str(open_shift.get("start_time", "")).strip()

    try:
        start_dt = parse_dt(start_time_raw)
    except Exception:
        await state.clear()
        await message.answer(
            f"❌ Некорректное время начала смены: {start_time_raw}",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
        return

    duration_minutes = int((end_dt - start_dt).total_seconds() // 60)
    if duration_minutes < 0:
        duration_minutes = 0

    rounded_hours = round_hours_from_minutes(duration_minutes)
    comment = "" if message.text.strip() == "Нет" else message.text.strip()

    try:
        sheets.close_shift(
            row_index=row_index,
            end_time=end_time_str,
            description=data.get("description", ""),
            comment=comment,
            duration_raw=duration_minutes,
            duration_rounded=rounded_hours,
        )
        await state.clear()
        await message.answer(
            f"✅ Смена закрыта.\n\n"
            f"🕒 Отработано: {duration_minutes} мин.\n"
            f"⏱ В табель: {rounded_hours} ч.\n"
            f"📝 Сделано: {data.get('description', '')}",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Ошибка при закрытии смены: {e}",
            reply_markup=menu_for_user(sheets, message.from_user.id),
        )
