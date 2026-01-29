from aiogram.fsm.state import State, StatesGroup


class ActivationFlow(StatesGroup):
    waiting_pocket_id = State()


class WorkFlow(StatesGroup):
    choosing_pair = State()
    choosing_expiry = State()


class BroadcastFlow(StatesGroup):
    waiting_content = State()
    waiting_confirmation = State()
