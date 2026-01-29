import aiohttp
from bot.config import settings


def _base_url() -> str:
    env = (settings.oanda_env or "practice").lower().strip()
    if env == "live":
        return "https://api-fxtrade.oanda.com"
    return "https://api-fxpractice.oanda.com"


def pair_to_instrument(pair: str) -> str:
    # "EUR/USD" -> "EUR_USD"
    return pair.replace(" ", "").replace("/", "_").upper()


def expiry_to_granularity(expiry_min: int) -> str:
    # OANDA granularities: M1, M5, M15, M30, H1, ...
    # Мы анализируем в логике экспирации 1/3/5 минут:
    # 1 и 3 — берём M1 (точнее), 5 — M5.
    if expiry_min <= 3:
        return "M1"
    return "M5"


def price_digits(pair: str) -> int:
    # JPY- пары обычно котируются до 3 знаков
    return 3 if "JPY" in pair.upper() else 5


async def fetch_candles_mid(pair: str, expiry_min: int, count: int | None = None) -> list[dict]:
    """Возвращает список свечей (старые -> новые) в формате:
    [{"t": str, "o": float, "h": float, "l": float, "c": float}, ...]

    Используем MID цены (price=M), чтобы не зависеть от bid/ask.
    """
    if not settings.oanda_api_token:
        raise RuntimeError("OANDA token is empty (OANDA_API_TOKEN)")

    instrument = pair_to_instrument(pair)
    granularity = expiry_to_granularity(expiry_min)
    base = _base_url()

    params = {
        "price": "M",
        "granularity": granularity,
        "count": int(count or settings.oanda_candles_count),
        "smooth": "true",
    }

    headers = {
        "Authorization": f"Bearer {settings.oanda_api_token}",
        "Content-Type": "application/json",
    }

    url = f"{base}/v3/instruments/{instrument}/candles"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=20) as r:
            data = await r.json()

    candles = data.get("candles") or []
    out: list[dict] = []

    for c in candles:
        # берём только завершённые свечи
        if not c.get("complete"):
            continue
        mid = c.get("mid") or {}
        out.append({
            "t": c.get("time"),
            "o": float(mid.get("o")),
            "h": float(mid.get("h")),
            "l": float(mid.get("l")),
            "c": float(mid.get("c")),
        })

    return out


async def fetch_candles_mid_granularity(pair: str, granularity: str, count: int | None = None) -> list[dict]:
    """То же, что fetch_candles_mid, но granularity задаётся явно (например 'H1', 'D')."""
    if not settings.oanda_api_token:
        raise RuntimeError("OANDA token is empty (OANDA_API_TOKEN)")

    instrument = pair_to_instrument(pair)
    base = _base_url()

    params = {
        "price": "M",
        "granularity": granularity,
        "count": int(count or settings.oanda_candles_count),
        "smooth": "true",
    }

    headers = {
        "Authorization": f"Bearer {settings.oanda_api_token}",
    }

    url = f"{base}/v3/instruments/{instrument}/candles"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=20) as r:
            data = await r.json()

    candles = data.get("candles") or []
    out: list[dict] = []

    for c in candles:
        if not c.get("complete"):
            continue
        mid = c.get("mid") or {}
        out.append({
            "t": c.get("time"),
            "o": float(mid.get("o")),
            "h": float(mid.get("h")),
            "l": float(mid.get("l")),
            "c": float(mid.get("c")),
        })

    return out


async def fetch_candles_mid_granularity(pair: str, granularity: str, count: int | None = None) -> list[dict]:
    """То же, что fetch_candles_mid, но granularity задаётся явно (например 'H1', 'D').

    Возвращает список свечей (старые -> новые) в формате:
    [{"t": str, "o": float, "h": float, "l": float, "c": float}, ...]
    """
    if not settings.oanda_api_token:
        raise RuntimeError("OANDA token is empty (OANDA_API_TOKEN)")

    instrument = pair_to_instrument(pair)
    base = _base_url()

    params = {
        "price": "M",
        "granularity": str(granularity).upper().strip(),
        "count": int(count or settings.oanda_candles_count),
        "smooth": "true",
    }

    headers = {
        "Authorization": f"Bearer {settings.oanda_api_token}",
        "Content-Type": "application/json",
    }

    url = f"{base}/v3/instruments/{instrument}/candles"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=20) as r:
            data = await r.json()

    candles = data.get("candles") or []
    out: list[dict] = []
    for c in candles:
        if not c.get("complete"):
            continue
        mid = c.get("mid") or {}
        out.append({
            "t": c.get("time"),
            "o": float(mid.get("o")),
            "h": float(mid.get("h")),
            "l": float(mid.get("l")),
            "c": float(mid.get("c")),
        })
    return out
