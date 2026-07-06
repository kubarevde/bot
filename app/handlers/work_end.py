from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards.main_menu import cancel_keyboard, main_menu_keyboard
from app.services.sheets import SheetsClient
from app.states.workday import EndWork

router = Router()


@router.message(F.text == "🔴 Закончил работу")
async def work_end_begin(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    row_index = sheets.get_open_shift_row_index(message.from_user.id)
    if not row_index:
        await message.answer(
            "ℹ️ Нет открытой смены.\nСначала нажми «🟢 Начал работу».",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.update_data(row_index=row_index)
    await state.set_state(EndWork.description)
    await message.answer(
        "📝 Что сделал? Кратко опиши выполненную работу:",
        reply_markup=cancel_keyboard(),
    )


@router.message(EndWork.description)
async def work_end_description(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return

    await state.update_data(description=message.text)
    await state.set_state(EndWork.comment)
    await message.answer(
        "💬 Дополнительный комментарий (или «нет»):",
        reply_markup=cancel_keyboard(),
    )


@router.message(EndWork.comment)
async def work_end_comment(message: Message, state: FSMContext, sheets: SheetsClient) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return

    data = await state.get_data()
    now = datetime.now()
    end_time_str = now.isoformat(timespec="seconds")
    comment = "" if message.text.lower() in ("нет", "no", "-") else message.text

    # Получаем start_time из листа
    sheet = sheets.work_log_sheet()
    row_values = sheet.row_values(data["row_index"])
    start_time_str = row_values[5] if len(row_values) > 5 else ""
    duration_raw = 0
    duration_rounded = 0.0

    if start_time_str:
        try:
            start_dt = datetime.fromisoformat(start_time_str)
            delta: timedelta = now - start_dt
            duration_raw = int(delta.total_seconds() // 60)
            # Округление до 0.5ч
            hours_raw = delta.total_seconds() / 3600
            duration_rounded = round(hours_raw * 2) / 2
        except ValueError:
            pass

    try:
        sheets.close_shift(
            row_index=data["row_index"],
            end_time=end_time_str,
            description=data["description"],
            comment=comment,
            duration_raw=duration_raw,
            duration_rounded=duration_rounded,
        )
        await state.clear()
        hours_display = f"{duration_rounded:.1f} ч" if duration_rounded else "—"
        await message.answer(
            f"✅ Смена закрыта!\n\n"
            f"📝 Что сделано: {data['description']}\n"
            f"🕐 Конец: {end_time_str}\n"
            f"⏱ Продолжительность: {hours_display}",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        await state.clear()
        await message.answer(
            "❌ Ошибка при закрытии смены. Сообщите администратору.",
            reply_markup=main_menu_keyboard(),
        )
