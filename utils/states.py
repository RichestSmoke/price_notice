from aiogram.fsm.state import State, StatesGroup

class NewNoticeState(StatesGroup):
    enter_data = State()
    add_order = State()
    add_pair = State()
    

class DeleteNoticeState(StatesGroup):
    start_del = State()
    order_del = State()
    coin_del = State()
    db_del = State()


class ConficTradeState(StatesGroup):
    start = State()