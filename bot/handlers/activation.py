import asyncio
import time

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.config import settings
from bot.keyboards.inline import (
    kb_activation_options,
    kb_to_workspace,
    kb_deposit_check,
)
from bot.services.user_store import user_store
from bot.states import ActivationFlow
from bot.services.pocketoption.client import PocketOptionClient

router = Router()
po = PocketOptionClient()
DELAY_SEC = 3


async def _delete_messages(bot, chat_id, message_ids):
    if not message_ids:
        return
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except TelegramBadRequest:
            continue


async def _record_activation_message(state: FSMContext, message_id: int):
    data = await state.get_data()
    ids = list(data.get("activation_message_ids") or [])
    ids.append(message_id)
    await state.update_data(activation_message_ids=ids)


async def clear_activation_context(message, state: FSMContext):
    data = await state.get_data()
    if isinstance(message, CallbackQuery):
        chat_id = message.message.chat.id
        bot_instance = message.bot
    else:
        chat_id = message.chat.id
        bot_instance = message.bot
    await _delete_messages(bot_instance, chat_id, data.get("activation_message_ids"))
    await _delete_messages(bot_instance, chat_id, data.get("deposit_message_ids"))
    await state.update_data(activation_message_ids=[], deposit_message_ids=[])


async def _send_and_track(state: FSMContext, send_coro):
    msg = await send_coro
    await _record_activation_message(state, msg.message_id)
    await asyncio.sleep(DELAY_SEC)
    return msg


send_and_track = _send_and_track


async def _maybe_send_activation_reminder(message: Message, state: FSMContext, status):
    reminder_base = status.deposit_updated_at or status.registered_at
    if not reminder_base:
        return
    if time.time() - reminder_base < 2 * 24 * 3600:
        return
    reminder_text = (
        "👋 Привет! Ты не завершил активацию бота!\n\n"
        "❗️To Чтобы получить доступ к полному потенциалу Бота, тебе нужно активировать его как можно скорее! \n\n"
        "✍️ Если забыл, как активировать бота, вот инструкция:\n\n"
        "1. Регистрируйся на торговой платформе и пополните счет👇\n"
        "https://pocket-option.ai\n"
        "2. Отправь свой торговый ID в бот, чтобы запустить его.\n"
        "3. Получи свой первый сигнал и начните торговать.\n\n"
        "🧑‍💻 Если тебе нужна помощь на любом этапе активации, пиши мне, буду рад помочь @FominovTrade"
    )
    await _send_and_track(state, message.answer(reminder_text))


async def _send_deposit_instructions(message: Message, state: FSMContext, pocket_id: str, status):
    await clear_activation_context(message, state)
    deposit_threshold = float(settings.pocketoption_min_deposit_usd or 0.0)
    deposit_display = max(1.0, deposit_threshold)
    intro_text = (
        "✅ Твой аккаунт найден в базе! Остался последний шаг - соверши пополнение "
        f"своего аккаунта на сумму от ${deposit_display:.0f}.\n\n"
        "Исходя из активности пользователей за сегодня, рекомендуемая средняя сумма депозита составляет $108.\n\n"
        f"❓ Возникают проблемы с активацией бота? - Пиши 👉 @{settings.support_username}"
    )
    message_ids = []
    intro_msg = await _send_and_track(state, message.answer(intro_text))
    message_ids.append(intro_msg.message_id)

    instruction_text = "🪙 Вот небольшая инструкция по пополнению депозита"
    if settings.pocketoption_deposit_instruction_url:
        instruction_text += f" ➡️ {settings.pocketoption_deposit_instruction_url}"
    instruction_msg = await _send_and_track(state, message.answer(instruction_text))
    message_ids.append(instruction_msg.message_id)

    reminder_msg = await _send_and_track(state, message.answer(
        "➡️ После пополнения (или если у тебя уже есть депозит) скорее нажимай кнопку ниже "
        "для получения доступа к торговому боту",
        reply_markup=kb_deposit_check()
    ))
    message_ids.append(reminder_msg.message_id)

    await state.update_data(
        pocket_id=pocket_id,
        deposit_message_ids=message_ids,
    )
    await _maybe_send_activation_reminder(message, state, status)


async def _grant_access(message: Message, state: FSMContext):
    await clear_activation_context(message, state)
    await state.clear()
    await _send_and_track(state, message.answer(
        "✅ Депозит подтверждён, доступ открыт!\n"
        "Теперь, можешь переходить к работе с ботом."
    ))
    await _send_and_track(state, message.answer(
        f"Перед началом работы с ботом, ознакомься с простой инструкцией по основным его функциям ➡️ {settings.bot_guide_video}"
    ))
    await _send_and_track(state, message.answer("👇 Перейти дальше:", reply_markup=kb_to_workspace()))


@router.callback_query(F.data == "activate")
async def on_activate(cb: CallbackQuery, state: FSMContext):
    await clear_activation_context(cb, state)
    await _send_and_track(state, cb.message.answer(
        "👉 Для активации бота и получения рабочей среды с 12 валютными парами и возможностью наблюдения "
        "за новостным фоном, тебе нужно создать новый аккаунт на брокере Pocket Option, по моей ссылке.\n\n"
        f"➡️ {settings.po_register_url}"
    ))
    await _send_and_track(state, cb.message.answer(f"➡️ Вот инструкция, которая поможет тебе пройти регистрацию {settings.po_register_video}"))
    await _send_and_track(state, cb.message.answer(
        "❗️ Кроме торгового бота, ты также получишь доступ к сигналам лично от меня, доступ к моей аналитике рынка "
        "и доступ к курсу по техническому анализу!\n\n"
        "⚠️ Регистрироваться обязательно по ссылке, иначе, бот не сможет подтвердить, что ты вступил в команду.\n\n"
        "❕ Важно: Не давай никому свой ID, так как бот выдается только на 1 аккаунт!\n\n"
        f"❓ Возникают проблемы с активацией бота? - Пиши 👉 @{settings.support_username}"
    ))
    await _send_and_track(state, cb.message.answer("👇 Выбери вариант:", reply_markup=kb_activation_options()))
    await cb.answer()


@router.callback_query(F.data == "reg_done")
async def on_reg_done(cb: CallbackQuery, state: FSMContext):
    await clear_activation_context(cb, state)
    await state.set_state(ActivationFlow.waiting_pocket_id)
    await _send_and_track(state, cb.message.answer("­❗️ Отлично!\n­❗️ Теперь, отправь мне свой новый ID на Pocket Option:"))
    await _send_and_track(state, cb.message.answer(f"­Как найти свой ID? ➡️ {settings.how_find_id_url}"))
    await cb.answer()


@router.callback_query(F.data == "check_deposit")
async def on_check_deposit(cb: CallbackQuery, state: FSMContext):
    await clear_activation_context(cb, state)
    data = await state.get_data()
    pocket_id = data.get("pocket_id")
    await state.set_state(ActivationFlow.waiting_pocket_id)
    if not pocket_id:
        await _send_and_track(state, cb.message.answer("⚠️ Я пока не знаю твой ID. Отправь его, чтобы я мог проверить депозит."))
        await cb.answer()
        return

    status = await po.get_status(pocket_id)
    if status.meets_deposit:
        await _grant_access(cb.message, state)
        await cb.answer()
        return

    await _send_deposit_instructions(cb.message, state, pocket_id, status)
    await cb.answer()


@router.callback_query(F.data == "already_have")
async def on_already_have(cb: CallbackQuery, state: FSMContext):
    await _send_and_track(state, cb.message.answer(
        "⚠️ Упс! Наш бот работает только с новыми аккаунтам PocketOption. "
        "Пожалуйста, зарегистрируйся по ссылке https://pocket-option.ai ⚠️\n\n"
        "Ознакомься с информацией, почему необходимо регистрировать новый аккаунт ➡️ https://youtu.be/NIj72pgCv70\n\n"
        f"❓ Возникают проблемы с активацией бота? - Пиши 👉 @{settings.support_username}"
    ))
    await cb.answer()


@router.message(ActivationFlow.waiting_pocket_id)
async def on_pocket_id(message: Message, state: FSMContext):
    pocket_id = (message.text or "").strip()

    if message.entities and any(e.type == "bot_command" for e in message.entities):
        return

    user_store.add(message.chat.id)

    if not pocket_id.isdigit() or len(pocket_id) < 4:
        await message.answer("Похоже, это не ID. Отправь, пожалуйста, только цифры (как в инструкции).")
        return

    status = await po.get_status(pocket_id)

    if not status.registered:
        await message.answer(
            "⚠️ Твой аккаунт не найден в базе! Пройди регистрацию по ссылке, "
            "после чего отправь мне свой ID на платформе PocketOption повторно\n\n"
            f"Ссылка для регистрации ➡️ {settings.po_register_url}\n\n"
            "После регистрации ты сможешь пользоваться ботом и получать неограниченное количество сигналов "
            "абсолютно бесплатно\n\n"
            f"❓ Возникают проблемы с активацией бота? - Пиши 👉 @{settings.support_username}"
        )
        return

    if not status.meets_deposit:
        await _send_deposit_instructions(message, state, pocket_id, status)
        return

    await _grant_access(message, state)
