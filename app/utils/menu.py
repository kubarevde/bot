from app.keyboards.main_menu import main_menu_keyboard, admin_menu_keyboard
from app.services.sheets import SheetsClient


def menu_for_user(sheets: SheetsClient, telegram_id: int):
    return admin_menu_keyboard() if sheets.is_admin(telegram_id) else main_menu_keyboard()