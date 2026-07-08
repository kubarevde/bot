from aiogram.fsm.state import State, StatesGroup


class StartWork(StatesGroup):
    location = State()
    work_type = State()
    equipment = State()
    comment = State()


class EndWork(StatesGroup):
    description = State()
    comment = State()


class AdminAddShift(StatesGroup):
    employee_code = State()
    start_time = State()
    end_time = State()
    location = State()
    work_type = State()
    equipment = State()
    description = State()
    comment = State()


class AdminCloseShift(StatesGroup):
    employee_code = State()
    end_time = State()
    description = State()
    comment = State()
