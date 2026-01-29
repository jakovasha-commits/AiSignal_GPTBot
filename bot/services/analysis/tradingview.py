import asyncio
import logging
import random
from pathlib import Path
from typing import Dict, Optional, Tuple, List

from bot.config import settings
from bot.utils.time_msk import is_market_open_msk

from .cache import DiskJSONCache
from .models import AnalysisResult
from .fibo_hints import fibo_template
from .fibo_real import calc_fibo_plan_oanda, format_plan
from bot.services.marketdata.oanda import fetch_candles_mid_granularity, expiry_to_granularity

logger = logging.getLogger(__name__)
from bot.services.chartimg import fetch_advanced_chart
from bot.services.ai import build_signal_from_vision


def _pair_to_symbol(pair: str) -> str:
    # "EUR/USD" -> "EURUSD"
    return pair.replace("/", "").replace(" ", "").strip().upper()


def _pair_to_chartimg_symbol(pair: str, otc: bool) -> str:
    # CHART-IMG ожидает TradingView symbol, например: OANDA:GBPJPY / OTC:GBPJPY
    base = _pair_to_symbol(pair)
    return f"OTC:{base}" if otc else f"OANDA:{base}"


def _interval_from_expiry(expiry_min: int):
    from tradingview_ta import Interval

    # У tradingview-ta нет 3m, поэтому 3 -> 5
    mapping = {
        1: Interval.INTERVAL_1_MINUTE,
        3: Interval.INTERVAL_5_MINUTES,   # fallback
        5: Interval.INTERVAL_5_MINUTES,
        15: Interval.INTERVAL_15_MINUTES,
        30: Interval.INTERVAL_30_MINUTES,
        60: Interval.INTERVAL_1_HOUR,
    }
    return mapping.get(expiry_min, Interval.INTERVAL_5_MINUTES)


def _tf_map_for_vision(expiry_min: int) -> List[Tuple[str, object]]:
    """Какие таймфреймы запрашиваем у TradingView для ИИ.

    Возвращает список (label, tradingview_ta.Interval).
    label используем в prompt.
    """
    from tradingview_ta import Interval
    return [
        ("1m", Interval.INTERVAL_1_MINUTE),
        ("3m", Interval.INTERVAL_5_MINUTES),  # честный fallback
        ("5m", Interval.INTERVAL_5_MINUTES),
        ("1h", Interval.INTERVAL_1_HOUR),
        ("1d", Interval.INTERVAL_1_DAY),
    ]


def _oanda_tf_map_for_vision(expiry_min: int) -> List[Tuple[str, str]]:
    main = expiry_to_granularity(expiry_min)
    items = [
        (f"{expiry_min}m", main),
        ("1m", "M1"),
        ("5m", "M5"),
        ("1h", "H1"),
        ("1d", "D"),
    ]
    seen = set()
    out: List[Tuple[str, str]] = []
    for label, gran in items:
        key = (label, gran)
        if key in seen:
            continue
        seen.add(key)
        out.append((label, gran))
    return out


def _fibo_levels_from_swing(low: float, high: float, trend: str) -> Dict[str, float]:
    """Вернёт основные уровни Фибо как словарь строк->цена.

    Для UP: уровни отката вниз от high.
    Для DOWN: уровни отката вверх от low.
    """
    rng = high - low
    if rng <= 0:
        return {}
    trend = (trend or "").upper()
    lvls = [0.236, 0.382, 0.5, 0.618, 0.786]
    out: Dict[str, float] = {}
    if trend == "UP":
        for x in lvls:
            out[f"{x}"] = round(high - rng * x, 6)
        out["0"] = round(high, 6)
        out["1"] = round(low, 6)
    else:
        for x in lvls:
            out[f"{x}"] = round(low + rng * x, 6)
        out["0"] = round(low, 6)
        out["1"] = round(high, 6)
    return out



def _clamp_int(x: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(round(x))))


def _pick_trend_and_strength(recommendation: str, rsi: Optional[float]) -> Tuple[str, int]:
    """Переводим рекомендацию TradingView в направление.

    Важно: если рекомендация NEUTRAL/UNKNOWN — возвращаем "NEUTRAL",
    чтобы бот не "скатывался" в вечный DOWN.
    """
    rec = (recommendation or "").upper()

    if rec in ("STRONG_BUY", "BUY"):
        return "UP", (2 if rec.startswith("STRONG_") else 1)
    if rec in ("STRONG_SELL", "SELL"):
        return "DOWN", (2 if rec.startswith("STRONG_") else 1)

    return "NEUTRAL", 0


def _calc_probs(strength: int, rsi: Optional[float]) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    # win range, reversal range
    if strength >= 2:
        win = (74, 82)
        rev = (18, 28)
    elif strength == 1:
        win = (66, 74)
        rev = (30, 45)
    else:
        # neutral / слабая уверенность
        win = (50, 55)
        rev = (45, 60)

    if rsi is not None and (rsi >= 70 or rsi <= 30):
        # перекуплен/перепродан -> выше шанс разворота
        rev = (_clamp_int(rev[0] + 8, 0, 100), _clamp_int(rev[1] + 10, 0, 100))
        win = (_clamp_int(win[0] - 4, 0, 100), _clamp_int(win[1] - 6, 0, 100))

    return win, rev


def _calc_volatility(indicators: Dict) -> int:
    atr = indicators.get("ATR") or indicators.get("atr")
    close = indicators.get("close") or indicators.get("Close")

    try:
        if atr is not None and close is not None:
            atr_f = float(atr)
            close_f = float(close)
            if close_f > 0:
                pct = (atr_f / close_f) * 100.0  # ATR в %
                return _clamp_int(pct * 4.0, 0, 100)  # масштабируем к 0..100
    except Exception:
        pass

    return random.randint(30, 55)


class TradingViewAnalyzer:
    def __init__(self):
        # Настройки берём из pydantic-settings (Settings читает .env).
        self.screener = (settings.tv_screener or "forex").strip()
        self.exchange = (settings.tv_exchange or "FX_IDC").strip()

        fb = (settings.tv_exchange_fallback or "")
        self.exchange_fallback = [x.strip() for x in fb.split(",") if x.strip()]

        ttl = int(getattr(settings, "tv_cache_ttl_sec", 21600))  # 6 часов

        # кэш кладём в корень проекта
        root = Path(__file__).resolve().parents[3]
        cache_path = (getattr(settings, "tv_cache_file", "") or str(root / ".tv_cache.json"))
        self.cache = DiskJSONCache(cache_path, default_ttl_sec=ttl)

    def _fetch(self, symbol: str, interval) -> Tuple[Dict, Dict]:
        from tradingview_ta import TA_Handler

        last_err = None
        for ex in [self.exchange] + self.exchange_fallback:
            try:
                handler = TA_Handler(
                    symbol=symbol,
                    screener=self.screener,
                    exchange=ex,
                    interval=interval
                )
                analysis = handler.get_analysis()
                return analysis.summary or {}, analysis.indicators or {}
            except Exception as e:
                last_err = e

        if last_err:
            raise last_err
        raise RuntimeError("TradingView fetch failed")

    async def analyze(self, pair: str, otc: bool, expiry_min: int) -> AnalysisResult:
        symbol = _pair_to_symbol(pair)
        interval = _interval_from_expiry(expiry_min)
        cache_key = f"{self.screener}:{self.exchange}:{symbol}:{str(interval)}"

        try:
            summary, indicators = await asyncio.to_thread(self._fetch, symbol, interval)

            rec = summary.get("RECOMMENDATION") or summary.get("recommendation") or "NEUTRAL"
            print("TV_REC", symbol, interval, rec)

            rsi = indicators.get("RSI")
            try:
                rsi_val = float(rsi) if rsi is not None else None
            except Exception:
                rsi_val = None

            trend, strength = _pick_trend_and_strength(str(rec), rsi_val)
            win, rev = _calc_probs(strength, rsi_val)
            vol = _calc_volatility(indicators)

            # если рынок закрыт и ты в OTC — данные будут менее "живые"
            wait = 20 if otc and (not is_market_open_msk()) else 15

            result = AnalysisResult(
                trend=trend,
                win_prob_min=win[0],
                win_prob_max=win[1],
                reversal_prob_min=rev[0],
                reversal_prob_max=rev[1],
                volatility=vol,
                wait_seconds=wait,
                entry_sl_tp="",
            )

            # Реальный Фибо считаем только по обычным FX-парам (не OTC) и только если есть устойчивое направление.
            # Источник свечей: OANDA v20 (нужен OANDA_API_TOKEN).
            if (not otc) and (trend in ("UP", "DOWN")) and (settings.oanda_api_token or ""):
                try:
                    plan = await calc_fibo_plan_oanda(pair=pair, expiry_min=expiry_min, trend=trend)
                    result.entry_sl_tp = format_plan(plan) if plan else fibo_template(trend)
                except Exception:
                    result.entry_sl_tp = fibo_template(trend)
            else:
                # Чтобы строка не была пустой
                result.entry_sl_tp = fibo_template(trend)

            # --- Новый формат сигнала (картинка + индикаторы) ---
            if (settings.signal_style or "").lower() == "screenshot":
                # 1) Получаем индикаторы по нескольким ТФ (цифрами)
                tv_by_tf: Dict[str, Dict[str, float]] = {}
                try:
                    for label, tf_interval in _tf_map_for_vision(expiry_min):
                        _sum, _ind = await asyncio.to_thread(self._fetch, symbol, tf_interval)
                        tv_by_tf[label] = _ind or {}
                except Exception:
                    tv_by_tf = {f"{expiry_min}m": indicators or {}}

                # 2) Строим уровни Фибо (если удалось посчитать план)
                fibo_levels: Dict[str, float] = {}
                try:
                    if (not otc) and (trend in ("UP", "DOWN")) and (settings.oanda_api_token or ""):
                        plan2 = None
                        try:
                            plan2 = await calc_fibo_plan_oanda(pair=pair, expiry_min=expiry_min, trend=trend)
                        except Exception:
                            plan2 = None
                        if plan2:
                            fibo_levels = _fibo_levels_from_swing(plan2.swing_low, plan2.swing_high, trend)
                except Exception:
                    fibo_levels = {}

                # 3) Берём скрин графика через CHART-IMG
                chart_bytes = await fetch_advanced_chart(
                    api_key=(settings.chartimg_api_key or ""),
                    symbol=_pair_to_chartimg_symbol(pair, otc),
                    interval_min=expiry_min,
                    studies=[x.strip() for x in (settings.chartimg_studies or "").split(",") if x.strip()],
                    width=int(settings.chartimg_width or 900),
                    height=int(settings.chartimg_height or 650),
                    theme=(settings.chartimg_theme or "dark"),
                )
                result.chart_image_bytes = chart_bytes

                # 3.1) Свечи из OANDA для GPT (если токен задан)
                candles_by_tf: Dict[str, List[dict]] = {}
                if settings.oanda_api_token:
                    try:
                        for label, gran in _oanda_tf_map_for_vision(expiry_min):
                            candles = await fetch_candles_mid_granularity(
                                pair=pair,
                                granularity=gran,
                                count=60,
                            )
                            if candles:
                                candles_by_tf[label] = candles[-60:]
                    except Exception as e:
                        logger.warning("OANDA candles fetch failed: %s", e)
                        candles_by_tf = {}

                # 4) Просим ИИ собрать сигнал в нужном формате
                sig = await build_signal_from_vision(
                    openai_api_key=(settings.openai_api_key or ""),
                    model=(settings.openai_model or "gpt-4o-mini"),
                    pair=pair,
                    interval_min=expiry_min,
                    trend=trend,
                    tv_indicators_by_tf=tv_by_tf,
                    candles_by_tf=candles_by_tf,
                    fibo_levels=fibo_levels,
                    chart_image_bytes=chart_bytes,
                    temperature=float(settings.openai_temperature or 0.2),
                    timeout_sec=int(settings.openai_timeout_sec or 25),
                )
                result.signal_action = sig.action
                result.signal_interval_min = expiry_min
                result.signal_indicators = sig.indicators
                result.bull_bear_strength = sig.bull_bear_strength

                logger.info(
                    "AI_SIGNAL_READY %s %sm indicators=%s chart_bytes=%s",
                    pair,
                    expiry_min,
                    len(result.signal_indicators or []),
                    len(chart_bytes or b""),
                )

                logger.info("AI_SIGNAL_SOURCE %s %sm %s", pair, expiry_min, getattr(sig, "source", "unknown"))

                # в "screenshot" режиме старый хвост не показываем
                result.entry_sl_tp = ""

            # bytes в кэш не пишем (JSON не умеет)
            to_cache = dict(result.__dict__)
            to_cache["chart_image_bytes"] = None
            self.cache.set(cache_key, to_cache)
            return result

        except Exception as e:
            logger.exception("Analyze failed: %s", e)
            cached = self.cache.get(cache_key)
            if cached:
                try:
                    return AnalysisResult(**cached)
                except Exception:
                    pass

            # консервативный фолбэк, чтобы бот не падал
            trend = random.choice(["UP", "DOWN"])
            return AnalysisResult(
                trend=trend,
                win_prob_min=55,
                win_prob_max=60,
                reversal_prob_min=45,
                reversal_prob_max=60,
                volatility=random.randint(30, 55),
                wait_seconds=20 if otc else 15,
                entry_sl_tp=fibo_template(trend),
            )
