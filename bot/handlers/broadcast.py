from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

from bot.config import settings
from bot.handlers.activation import clear_activation_context
from bot.keyboards.inline import kb_broadcast_controls
from bot.services.approved_store import approved_store
from bot.services.user_store import user_store
from bot.states import BroadcastFlow

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("add"))
async def cmd_add(message: Message):
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Используй /add <chat_id>, чтобы добавить пользователя.")
        return
    target_id = int(parts[1])
    approved_store.add(target_id)
    await message.answer(f"Пользователь {target_id} добавлен в одобренные.")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    await clear_activation_context(message, state)
    await state.set_state(BroadcastFlow.waiting_content)
    await state.update_data(broadcast_text="", broadcast_photo=None, preview_message_id=None)
    await message.answer(
        "📣 Отправь текст и/или фото для рассылки. "
        "Фото нужно прикрепить как обычное изображение, подпись будет использоваться как текст."
    )


@router.message(BroadcastFlow.waiting_content)
async def compose_broadcast(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or message.caption or "").strip()
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    if not text and not photo_id:
        await message.answer("Нужно отправить текст и/или фото.")
        return

    data = await state.get_data()
    preview_id = data.get("preview_message_id")
    if preview_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=preview_id)
        except TelegramBadRequest:
            pass

    if photo_id:
        preview = await message.answer_photo(
            photo=photo_id,
            caption=text or None,
            reply_markup=kb_broadcast_controls()
        )
    else:
        preview = await message.answer(text, reply_markup=kb_broadcast_controls())

    await state.update_data(
        broadcast_text=text,
        broadcast_photo=photo_id,
        preview_message_id=preview.message_id,
    )
    await state.set_state(BroadcastFlow.waiting_confirmation)


@router.callback_query(BroadcastFlow.waiting_confirmation, F.data == "broadcast_send")
async def broadcast_send(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    recipients = user_store.list()
    text = data.get("broadcast_text") or ""
    photo_id = data.get("broadcast_photo")
    sent = 0
    for chat_id in recipients:
        try:
            if photo_id:
                await cb.bot.send_photo(chat_id=chat_id, photo=photo_id, caption=text or None)
            else:
                await cb.bot.send_message(chat_id=chat_id, text=text)
            sent += 1
        except TelegramBadRequest:
            continue
        except Exception:
            continue

    try:
        await cb.message.delete()
    except TelegramBadRequest:
        pass

    await cb.answer(f"Рассылка отправлена ({sent}/{len(recipients)})")
    await state.clear()


@router.callback_query(BroadcastFlow.waiting_confirmation, F.data == "broadcast_cancel")
async def broadcast_cancel(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    try:
        await cb.message.delete()
    except TelegramBadRequest:
        pass

    await cb.answer("Рассылка отменена")
    await state.clear()
