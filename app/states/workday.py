from aiogram.fsm.state import State, StatesGroup


class StartWork(StatesGroup):
    location = State()
    geo = State()
    work_type = State()
    equipment = State()
    comment = State()


class EndWork(StatesGroup):
    description = State()
    comment = State()
