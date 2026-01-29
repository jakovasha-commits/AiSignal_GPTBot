from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from bot.services.marketdata.oanda import fetch_candles_mid, price_digits


@dataclass
class FiboPlan:
    entry: float
    sl: float
    tp1: float
    tp2: float
    swing_low: float
    swing_high: float
    granularity: str


def _fractal_swings(candles: list[dict], k: int = 3) -> tuple[list[int], list[int]]:
    """Возвращает индексы фракталов high/low на списке свечей (старые->новые)."""
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]

    hi_idx: list[int] = []
    lo_idx: list[int] = []

    for i in range(k, len(candles) - k):
        window_h = highs[i - k:i + k + 1]
        window_l = lows[i - k:i + k + 1]
        # строго, без равенств
        if highs[i] == max(window_h) and highs[i] > max(window_h[:k] + window_h[k + 1:]):
            hi_idx.append(i)
        if lows[i] == min(window_l) and lows[i] < min(window_l[:k] + window_l[k + 1:]):
            lo_idx.append(i)

    return hi_idx, lo_idx


def _last_impulse_for_trend(candles: list[dict], trend: str, k: int = 3) -> Optional[tuple[float, float]]:
    """Возвращает (low, high) последнего импульса, согласованного с трендом."""
    if len(candles) < (2 * k + 10):
        return None

    hi_idx, lo_idx = _fractal_swings(candles, k=k)
    if not hi_idx or not lo_idx:
        return None

    trend = (trend or "").upper()

    if trend == "UP":
        # ищем последний high, у которого есть low перед ним
        for hi in reversed(hi_idx):
            prev_lows = [lo for lo in lo_idx if lo < hi]
            if not prev_lows:
                continue
            lo = prev_lows[-1]
            low = candles[lo]["l"]
            high = candles[hi]["h"]
            if high > low:
                return low, high
        return None

    if trend == "DOWN":
        # ищем последний low, у которого есть high перед ним
        for lo in reversed(lo_idx):
            prev_highs = [hi for hi in hi_idx if hi < lo]
            if not prev_highs:
                continue
            hi = prev_highs[-1]
            low = candles[lo]["l"]
            high = candles[hi]["h"]
            if high > low:
                return low, high
        return None

    return None


def _round(x: float, digits: int) -> float:
    return round(float(x), digits)


def build_plan(trend: str, current: float, low: float, high: float, digits: int, granularity: str) -> FiboPlan:
    rng = high - low
    if rng <= 0:
        raise ValueError("Bad swing range")

    trend = (trend or "").upper()

    if trend == "UP":
        lvl50 = high - rng * 0.50
        lvl618 = high - rng * 0.618
        entry = lvl50 if abs(current - lvl50) < abs(current - lvl618) else lvl618

        sl = (high - rng * 0.786) - rng * 0.02
        tp1 = high + rng * 0.272
        tp2 = high + rng * 0.618
    else:
        lvl50 = low + rng * 0.50
        lvl618 = low + rng * 0.618
        entry = lvl50 if abs(current - lvl50) < abs(current - lvl618) else lvl618

        sl = (low + rng * 0.786) + rng * 0.02
        tp1 = low - rng * 0.272
        tp2 = low - rng * 0.618

    return FiboPlan(
        entry=_round(entry, digits),
        sl=_round(sl, digits),
        tp1=_round(tp1, digits),
        tp2=_round(tp2, digits),
        swing_low=_round(low, digits),
        swing_high=_round(high, digits),
        granularity=granularity,
    )


async def calc_fibo_plan_oanda(pair: str, expiry_min: int, trend: str) -> Optional[FiboPlan]:
    candles = await fetch_candles_mid(pair=pair, expiry_min=expiry_min)
    if len(candles) < 50:
        return None

    current = candles[-1]["c"]
    impulse = _last_impulse_for_trend(candles, trend=trend, k=3)
    if not impulse:
        return None

    low, high = impulse
    digits = price_digits(pair)

    # В свечах мы всегда возвращаем low<high, но на всякий
    if high < low:
        low, high = high, low

    # granularity уже зашита в fetch (M1/M5). Подпишем в тексте.
    granularity = "M1" if expiry_min <= 3 else "M5"

    return build_plan(trend=trend, current=current, low=low, high=high, digits=digits, granularity=granularity)


def format_plan(plan: FiboPlan) -> str:
    return (
        f"🎯 Точка входа: ~{plan.entry}\n"
        f"🛑 SL: {plan.sl}\n"
        f"🎯 TP: {plan.tp1} / {plan.tp2}"
    )
