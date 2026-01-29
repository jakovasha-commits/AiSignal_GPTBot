from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.activation import send_and_track
from bot.keyboards.inline import kb_activate, kb_to_workspace
from bot.services.approved_store import approved_store
from bot.services.user_store import user_store

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_store.add(message.chat.id)
    await send_and_track(state, message.answer("👋 Привет!"))

    await send_and_track(state, message.answer(
        "🤖 Я - торговый бот, основанный на искусственном интеллекте, в связке с 15 индикаторами."
    ))

    await send_and_track(state, message.answer(
        "📊 Я умею автоматически анализировать техничесные индикаторы графиков на любых таймфреймах, "
        "оценивать новостной фон и выдавать сигналы для торговли на бинарных опционах"
    ))

    final_text = (
        "🏆 Но это не золотые слитки, которые сами придут к вам в руки.\n\n"
        "🥇 Это не Грааль!\n"
        "💰 Это не кнопка Бабло!\n\n"
        "Это - лопата, с помощью которой вы сможете достать это самое золото.\n\n"
        "✅ Трейдинг – это не цель. Это путь, который ты должен пройти сам! Ну, а я помогу тебе в этом: "
        "я использую нейросетевой движок и множество индикаторов для анализа, и предоставляю платформу "
        "для лёгкого старта на Pocket Option!"
    )

    await send_and_track(state, message.answer(final_text, reply_markup=kb_activate()))

    if approved_store.contains(message.chat.id):
        await send_and_track(state, message.answer(
            "✅ Твоя заявка подтверждена — можешь переходить в рабочую область прямо сейчас.",
            reply_markup=kb_to_workspace()
        ))
