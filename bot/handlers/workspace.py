import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from bot.keyboards.inline import kb_pairs, kb_expiry, kb_new_signal
from bot.states import WorkFlow
from bot.utils.time_msk import is_market_open_msk
from bot.utils.formatters import pretty_pair
from bot.services.analysis import analyzer
from bot.config import settings
from bot.handlers.activation import clear_activation_context

router = Router()


@router.callback_query(F.data == "workspace")
async def on_workspace(cb: CallbackQuery, state: FSMContext):
    await clear_activation_context(cb, state)
    open_now = is_market_open_msk()

    await state.clear()
    await state.set_state(WorkFlow.choosing_pair)

    if open_now:
        text = (
            "💸 Приветствую в рабочей области!\n\n"
            " ↗️ Для начала работы с ботом:\n\n"
            "    ☑️ Выбери валютную пару из списка ниже\n"
            "    ☑️ Выбери нужные настройки для получения сигнала\n\n"
            "📊 После выбора настроек бот проведет короткий анализ и выдаст торговый сигнал\n\n"
            "👉 Выбери торговую пару из списка:"
        )
        await cb.message.answer(text, reply_markup=kb_pairs(otc=False))
    else:
        await cb.message.answer(
            "🏝 Сейчас рынок отдыхает!\n\n"
            "🗓 Мы поддерживаем анализ торгов биржевых активов в будние дни с 08:00 до 23:00 по МСК\n\n"
            "📊 Сейчас мы можем предложить анализ OTC-активов на PocketOption\n\n"
            "Для получения сигнала по OTC, выбери торговую пару"
        )
        await cb.message.answer("👇 Выбери торговую пару OTC:", reply_markup=kb_pairs(otc=True))

    await cb.answer()


@router.callback_query(F.data.startswith("pair:"))
async def on_pair(cb: CallbackQuery, state: FSMContext):
    _, pair, otc_flag = cb.data.split(":")
    otc = otc_flag == "1"

    await state.update_data(pair=pair, otc=otc)
    await state.set_state(WorkFlow.choosing_expiry)

    await cb.message.answer(
        f"Выбрана пара {pretty_pair(pair, otc)}\n\n⏳ Выбери желаемое время экспирации сигнала",
        reply_markup=kb_expiry()
    )
    await cb.answer()


@router.callback_query(WorkFlow.choosing_expiry, F.data.startswith("exp:"))
async def on_expiry(cb: CallbackQuery, state: FSMContext):
    expiry = int(cb.data.split(":")[1])
    data = await state.get_data()
    pair = data["pair"]
    otc = data["otc"]

    await state.update_data(expiry=expiry)

    await cb.message.answer(
        f"💸 Выбрана пара {pretty_pair(pair, otc)}\n\n⏳ Произвожу анализ...\n(это может занять какое-то время)"
    )
    await cb.answer("Запрос принят, анализирую...")

    result = await analyzer.analyze(pair=pair, otc=otc, expiry_min=expiry)
    await asyncio.sleep(1.0)

    if (result.trend or "").upper() == "NEUTRAL":
        await cb.message.answer(
            f"🟡 По {pretty_pair(pair, otc)} сейчас нет устойчивого тренда (TradingView: NEUTRAL).\n"
            "Сигнал не выдаю — попробуй другой таймфрейм или пару.\n\n"
        )
        await cb.message.answer("👇 Действие:", reply_markup=kb_new_signal())
        return

    trend_emoji = "🟢" if result.trend == "UP" else "🔴"
    trend_word = "ПОВЫШЕНИЕ" if result.trend == "UP" else "ПОНИЖЕНИЕ"

    if (settings.signal_style or "").lower() == "screenshot":
        if result.chart_image_bytes:

            photo = BufferedInputFile(result.chart_image_bytes, filename="chart.png")
            await cb.message.answer_photo(photo)

        action = (result.signal_action or ("ПОКУПКА" if result.trend == "UP" else "ПРОДАЖА")).upper()
        arrow = "↗️" if action == "ПОКУПКА" else "↘️"
        indicators_lines = "\n".join(
            [f"💠 GPT: {name} {val}" for name, val in (result.signal_indicators or [])]
        )
        if not indicators_lines:
            indicators_lines = "💠 GPT: RSI ?"

        await cb.message.answer(
            f"📊 Исходя из анализа индикаторов для пары {pretty_pair(pair, otc)}\n\n"
            f"✅ Действие: {action} {arrow}\n"
            f"⏱ Временной интервал: {expiry} МИНУТ\n\n"
            f"Основные индикаторы:\n"
            f"{indicators_lines}\n\n"
            f"🐂🐻 Бычья / Медвежья сила {round(float(result.bull_bear_strength or 0.0), 2)}"
        )
    else:
        await cb.message.answer(
            f"{trend_emoji} Обнаружен {'восходящий' if result.trend == 'UP' else 'нисходящий'} тренд и связки индикаторов для {'OTC-' if otc else ''}актива {pretty_pair(pair, otc)}\n\n"
            f"⏰ В выбранном временном отрезке, график {pretty_pair(pair, otc)} показывает тренд на {trend_emoji} {trend_word}\n\n"
            f"💠 Вероятность успешного входа: {result.win_prob_min} - {result.win_prob_max} %\n"
            f"💠 Вероятность разворота: {result.reversal_prob_min} - {result.reversal_prob_max} %\n"
            f"💠 Волатильность графика (относительное значение 0-100): {result.volatility}\n\n"
            f"Рекомендуется входить в сделку на {trend_emoji} {trend_word}\n\n"
            f"{result.entry_sl_tp}\n\n"
        )

    await cb.message.answer("👇 Действие:", reply_markup=kb_new_signal())


@router.callback_query(F.data == "new_signal")
async def on_new_signal(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "pair" not in data:
        await cb.message.answer("Сначала выбери торговую пару.")
        await cb.answer()
        return

    if "expiry" not in data:
        await cb.message.answer("⏳ Выбери время экспирации:", reply_markup=kb_expiry())
        await cb.answer()
        return

    pair = data["pair"]
    otc = data.get("otc", False)
    expiry = data["expiry"]

    await cb.message.answer(
        f"💸 {pretty_pair(pair, otc)}\n\n⏳ Произвожу анализ...\n(это может занять какое-то время)"
    )
    await cb.answer("Запрос принят, анализирую...")

    result = await analyzer.analyze(pair=pair, otc=otc, expiry_min=expiry)
    await asyncio.sleep(1.0)

    if (result.trend or "").upper() == "NEUTRAL":
        await cb.message.answer(
            f"🟡 По {pretty_pair(pair, otc)} сейчас нет устойчивого тренда (TradingView: NEUTRAL).\n"
            "Сигнал не выдаю — попробуй другой таймфрейм или пару.\n\n"
        )
        await cb.message.answer("👇 Действие:", reply_markup=kb_new_signal())
        await cb.answer()
        return

    trend_emoji = "🟢" if result.trend == "UP" else "🔴"
    trend_word = "ПОВЫШЕНИЕ" if result.trend == "UP" else "ПОНИЖЕНИЕ"

    if (settings.signal_style or "").lower() == "screenshot":
        if result.chart_image_bytes:
            photo = BufferedInputFile(result.chart_image_bytes, filename="chart.png")
            await cb.message.answer_photo(photo)
        action = (result.signal_action or ("ПОКУПКА" if result.trend == "UP" else "ПРОДАЖА")).upper()
        arrow = "↗️" if action == "ПОКУПКА" else "↘️"
        indicators_lines = "\n".join(
            [f"💠 GPT: {name} {val}" for name, val in (result.signal_indicators or [])]
        )
        if not indicators_lines:
            indicators_lines = "💠 GPT: RSI ?"

        await cb.message.answer(
            f"📊 Исходя из анализа индикаторов для пары {pretty_pair(pair, otc)}\n\n"
            f"✅ Действие: {action} {arrow}\n"
            f"⏱ Временной интервал: {expiry} МИНУТ\n\n"
            f"Основные индикаторы:\n"
            f"{indicators_lines}\n\n"
            f"🐂🐻 Бычья / Медвежья сила {round(float(result.bull_bear_strength or 0.0), 2)}"
        )
    else:
        await cb.message.answer(
            f"{trend_emoji} Найден тренд по {pretty_pair(pair, otc)}\n\n"
            f"💠 Вероятность успешного входа: {result.win_prob_min} - {result.win_prob_max} %\n"
            f"💠 Вероятность разворота: {result.reversal_prob_min} - {result.reversal_prob_max} %\n"
            f"💠 Волатильность: {result.volatility}\n\n"
            f"Рекомендуется входить на {trend_emoji} {trend_word}\n\n"
            f"{result.entry_sl_tp}\n\n"
        )

    await cb.message.answer("👇 Действие:", reply_markup=kb_new_signal())
    await cb.answer()
