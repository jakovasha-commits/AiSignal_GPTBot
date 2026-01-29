import base64
import json
import re
import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp

from bot.config import settings

OPENAI_CHAT_COMPLETIONS = "https://api.openai.com/v1/chat/completions"

log = logging.getLogger(__name__)
log.warning("[AI] vision_signal.py LOADED (module import)")


def _setup_ai_logger_level_once() -> None:
    """
    В контейнере часто root-логгер уже настроен.
    Но на всякий случай выставим уровень именно этому логгеру.
    """
    level_name = (getattr(settings, "ai_log_level", None) or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log.setLevel(level)


_setup_ai_logger_level_once()


def _safe_json(obj):
    if isinstance(obj, bytes):
        return {"__bytes__": True, "len": len(obj), "sha256": hashlib.sha256(obj).hexdigest()}
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json(x) for x in obj]
    return str(obj)


def _write_json_log(payload: dict, *, symbol: str, tf: str, event: str) -> None:
    if not getattr(settings, "ai_log_save_json", False):
        return
    log_dir = Path(getattr(settings, "ai_log_dir", "./data/ai_logs") or "./data/ai_logs")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        log.warning("AI log directory %s not writable: %s, falling back to /tmp/ai_logs", log_dir, exc)
        log_dir = Path("/tmp/ai_logs")
        log_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    fname = f"{ts}_{symbol}_{tf}_{event}.json".replace("/", "_")
    (log_dir / fname).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def log_ai_interaction(*, event: str, symbol: str, tf: str, inputs: dict,
                       response_text: str, model: str, latency_ms: int,
                       status: Optional[int] = None) -> None:
    """
    Пишем:
    - коротко в docker logs всегда (status/latency/model)
    - подробно (inputs + response trim) только при settings.ai_debug
    - в json-файл при settings.ai_log_save_json
    """
    base = {
        "event": event,
        "symbol": symbol,
        "tf": tf,
        "model": model,
        "status": status,
        "latency_ms": latency_ms,
        "inputs": _safe_json(inputs),
        "response_text": (response_text or "")[:4000],
    }

    # Короткая строка — всегда
    log.info("[AI] %s %s %s model=%s status=%s latency_ms=%s",
             event, symbol, tf, model, status, latency_ms)

    # Подробно — только в debug
    if getattr(settings, "ai_debug", False):
        log.info("[AI] payload: %s", json.dumps(base["inputs"], ensure_ascii=False))
        if response_text:
            log.info("[AI] response(trim): %s", (response_text or "")[:2000])

    _write_json_log(base, symbol=symbol, tf=tf, event=event)


@dataclass
class VisionSignal:
    action: str  # "ПОКУПКА"|"ПРОДАЖА"
    indicators: List[Tuple[str, str]]
    bull_bear_strength: float


def _b64_data_url(image_bytes: bytes, mime: str = "image/png") -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _safe_json_extract(text: str) -> Optional[dict]:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _fallback_signal(trend: str, main_indicators: Dict[str, float]) -> VisionSignal:
    action = "ПОКУПКА" if (trend or "").upper() == "UP" else "ПРОДАЖА"
    out: List[Tuple[str, str]] = []
    for key in ("CCI", "RSI", "Stoch.K", "Stoch.D", "ADX"):
        if key in main_indicators:
            try:
                out.append((key.replace("Stoch.", ""), str(round(float(main_indicators[key]), 2))))
            except Exception:
                out.append((key.replace("Stoch.", ""), str(main_indicators[key])))

    rsi = None
    try:
        rsi = float(main_indicators.get("RSI")) if main_indicators.get("RSI") is not None else None
    except Exception:
        rsi = None

    strength = 0.5
    if rsi is not None:
        strength = min(1.0, max(0.0, abs(rsi - 50.0) / 50.0))

    return VisionSignal(action=action, indicators=out, bull_bear_strength=round(float(strength), 2))


async def build_signal_from_vision(
    *,
    openai_api_key: str,
    model: str,
    pair: str,
    interval_min: int,
    trend: str,
    tv_indicators_by_tf: Dict[str, Dict[str, float]],
    candles_by_tf: Optional[Dict[str, List[dict]]] = None,
    fibo_levels: Dict[str, float],
    chart_image_bytes: Optional[bytes],
    temperature: float = 0.2,
    timeout_sec: int = 25,
) -> VisionSignal:
    main_tf_key = f"{interval_min}m"
    main = tv_indicators_by_tf.get(main_tf_key) or next(iter(tv_indicators_by_tf.values()), {})

    # Логируем входные данные (без base64)
    compact_ind = {}
    for tf, ind in (tv_indicators_by_tf or {}).items():
        take = {}
        for k in ("RSI", "CCI", "ADX", "MACD.macd", "MACD.signal", "MACD.hist", "Stoch.K", "Stoch.D"):
            if k in ind:
                take[k] = ind[k]
        compact_ind[tf] = take

    inputs_log = {
        "pair": pair,
        "interval_min": interval_min,
        "trend_from_tradingview": trend,
        "indicators_by_tf": compact_ind,
        "candles_by_tf": candles_by_tf or {},
        "fibo_levels": fibo_levels,
        "chart_image": _safe_json(chart_image_bytes) if chart_image_bytes else None,
        "temperature": float(temperature),
        "timeout_sec": int(timeout_sec),
    }

    # Fallback: если нет ключа или картинки
    if not openai_api_key or not chart_image_bytes:
        log_ai_interaction(
            event="fallback_no_key_or_image",
            symbol=pair,
            tf=main_tf_key,
            inputs=inputs_log,
            response_text="",
            model=model,
            latency_ms=0,
            status=None,
        )
        return _fallback_signal(trend, main)

    prompt = {
        "pair": pair,
        "interval_min": interval_min,
        "trend_from_tradingview": trend,
        "indicators_by_tf": compact_ind,
        "candles_by_tf": candles_by_tf or {},
        "fibo_levels": fibo_levels,
        "task": (
            "На основе скриншота графика, численных индикаторов и уровней Фибоначчи "
            "выдай торговый сигнал в виде JSON. Никаких объяснений, только JSON."
        ),
        "output_schema": {
            "action": "ПОКУПКА|ПРОДАЖА",
            "indicators": [{"name": "RSI", "value": "28"}, {"name": "CCI", "value": "-110"}],
            "bull_bear_strength": "число 0..1 (например 0.4)",
        },
        "rules": [
            "action должен быть согласован с трендом (UP->ПОКУПКА, DOWN->ПРОДАЖА), "
            "но допускай контр-сигнал если по Фибо + дивергенции высок шанс отката",
            "indicators: выбери 4-6 самых важных, значения округляй до разумных",
            "bull_bear_strength: 0..1, где 0.5 нейтрально, ближе к 1 сильный импульс",
            "никаких слов вне JSON",
        ],
    }

    img_url = _b64_data_url(chart_image_bytes)

    payload = {
        "model": model,
        "temperature": float(temperature),
        "messages": [
            {"role": "system", "content": "Ты строгий финансовый аналитик. Возвращай только валидный JSON по схеме."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": json.dumps(prompt, ensure_ascii=False)},
                    {"type": "image_url", "image_url": {"url": img_url}},
                ],
            },
        ],
    }

    headers = {"Authorization": f"Bearer {openai_api_key}", "Content-Type": "application/json"}

    t0 = time.time()
    status = None
    raw_text = ""
    data = None

    timeout = aiohttp.ClientTimeout(total=int(timeout_sec))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(OPENAI_CHAT_COMPLETIONS, headers=headers, json=payload) as resp:
            status = resp.status
            raw_text = await resp.text()
            try:
                data = json.loads(raw_text) if raw_text else None
            except Exception:
                data = None

    latency_ms = int((time.time() - t0) * 1000)

    # Лог: статус/латентность + при debug кусок ответа
    log_ai_interaction(
        event="openai_call",
        symbol=pair,
        tf=main_tf_key,
        inputs=inputs_log,
        response_text=raw_text,
        model=model,
        latency_ms=latency_ms,
        status=status,
    )

    if status != 200 or not isinstance(data, dict):
        return _fallback_signal(trend, main)

    text = ""
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        text = ""

    parsed = _safe_json_extract(text)
    if not isinstance(parsed, dict):
        return _fallback_signal(trend, main)

    action = str(parsed.get("action") or "").upper()
    if action not in ("ПОКУПКА", "ПРОДАЖА"):
        action = "ПОКУПКА" if (trend or "").upper() == "UP" else "ПРОДАЖА"

    raw_inds = parsed.get("indicators") or []
    out_inds: List[Tuple[str, str]] = []
    if isinstance(raw_inds, list):
        for item in raw_inds[:6]:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                val = str(item.get("value") or "").strip()
                if name and val:
                    out_inds.append((name, val))

    strength = parsed.get("bull_bear_strength")
    try:
        strength_f = float(strength)
    except Exception:
        strength_f = 0.5
    strength_f = max(0.0, min(1.0, strength_f))

    if not out_inds:
        return _fallback_signal(trend, main)

    return VisionSignal(action=action, indicators=out_inds, bull_bear_strength=round(strength_f, 2))
