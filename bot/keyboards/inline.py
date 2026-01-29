from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "USD/CAD",
    "NZD/USD",
    "EUR/JPY",
    "GBP/JPY",
    "EUR/GBP",
    "AUD/JPY",
    "EUR/AUD",
]

def kb_activate() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Активировать бота", callback_data="activate")]
    ])


def kb_activation_options() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Прошел регистрацию, проверь мой ID", callback_data="reg_done")],
        [InlineKeyboardButton(text="📯У меня уже есть свой аккаунт PocketOption", callback_data="already_have")],
    ])


def kb_to_workspace() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Перейти в рабочую область", callback_data="workspace")]
    ])


def kb_deposit_instructions(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Посмотреть инструкцию по депозиту", url=url)]
    ])


def kb_deposit_check() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Пополнен, проверь мой депозит", callback_data="check_deposit")]
    ])


def kb_broadcast_controls() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_send"),
            InlineKeyboardButton(text="🗑️ Удалить", callback_data="broadcast_cancel"),
        ]
    ])


def kb_pairs(otc: bool) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for p in PAIRS:
        row.append(InlineKeyboardButton(
            text=(p + (" OTC" if otc else "")),
            callback_data=f"pair:{p}:{1 if otc else 0}"
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_expiry() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏳1 М", callback_data="exp:1"),
            InlineKeyboardButton(text="⏳3 М", callback_data="exp:3"),
            InlineKeyboardButton(text="⏳5 М", callback_data="exp:5"),
        ]
    ])


def kb_new_signal() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♻️ Получить новый сигнал", callback_data="new_signal")]
    ])
