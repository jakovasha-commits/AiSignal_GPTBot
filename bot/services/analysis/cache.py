import json
import os
import time
from typing import Any, Dict, Optional


class DiskJSONCache:
    """Простой кэш на диске для фолбэка, если TradingView временно не отвечает."""

    def __init__(self, path: str, default_ttl_sec: int = 6 * 60 * 60):
        self.path = path
        self.default_ttl_sec = default_ttl_sec

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}

    def _save(self, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def get(self, key: str, ttl_sec: Optional[int] = None) -> Optional[Dict[str, Any]]:
        ttl = self.default_ttl_sec if ttl_sec is None else ttl_sec
        data = self._load()
        item = data.get(key)
        if not isinstance(item, dict):
            return None
        ts = item.get("ts")
        if not isinstance(ts, (int, float)):
            return None
        if time.time() - float(ts) > ttl:
            return None
        return item.get("value")

    def set(self, key: str, value: Dict[str, Any]) -> None:
        data = self._load()
        data[key] = {"ts": time.time(), "value": value}
        self._save(data)
