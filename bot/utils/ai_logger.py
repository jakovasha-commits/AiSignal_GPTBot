# bot/utils/ai_logger.py
import json
import os
import time
import hashlib
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional

AI_DEBUG = os.getenv("AI_DEBUG", "0") == "1"
AI_LOG_SAVE_JSON = os.getenv("AI_LOG_SAVE_JSON", "1") == "1"
AI_LOG_DIR = os.getenv("AI_LOG_DIR", "./data/ai_logs")


def _safe_json(obj: Any) -> Any:
    """Конвертация в JSON-friendly формат без падений."""
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, bytes):
        return {"__bytes__": True, "len": len(obj), "sha256": hashlib.sha256(obj).hexdigest()}
    if isinstance(obj, dict):
        return {str(k): _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json(x) for x in obj]
    return str(obj)


def log_ai_exchange(logger, *, event: str, symbol: str, tf: str,
                    inputs: Dict[str, Any], response_text: str,
                    response_json: Optional[Dict[str, Any]] = None,
                    model: Optional[str] = None,
                    latency_ms: Optional[int] = None):
    """Логирует вводные данные и ответ модели. При AI_DEBUG=0 делает минимум."""
    base = {
        "event": event,
        "symbol": symbol,
        "tf": tf,
        "model": model,
        "latency_ms": latency_ms,
        "inputs": _safe_json(inputs),
        "response_text": response_text[:4000],  # ограничим, чтобы не убить journald
        "response_json": _safe_json(response_json) if response_json else None,
    }

    if AI_DEBUG:
        logger.info("[AI] %s", json.dumps(base, ensure_ascii=False))
    else:
        # В “обычном” режиме логируем только факт и краткий итог
        logger.info("[AI] event=%s symbol=%s tf=%s model=%s latency_ms=%s",
                    event, symbol, tf, model, latency_ms)

    if AI_LOG_SAVE_JSON:
        os.makedirs(AI_LOG_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        fname = f"{AI_LOG_DIR}/{ts}_{symbol}_{tf}_{event}.json".replace("/", "_")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(base, f, ensure_ascii=False, indent=2)
