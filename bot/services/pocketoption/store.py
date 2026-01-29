from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, Optional

log = logging.getLogger(__name__)


@dataclass
class PocketOptionRecord:
    pocket_id: str
    registered_at: Optional[float] = None
    deposit_amount: float = 0.0
    deposit_updated_at: Optional[float] = None
    last_seen: float = 0.0


class PocketOptionStore:
    """Проще всего — хранить список ID на диске, обновляя при приходе постбэков."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._lock = Lock()
        self._records: Dict[str, PocketOptionRecord] = self._load()

    def _load(self) -> Dict[str, PocketOptionRecord]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("PocketOption store load failed (%s), starting fresh", exc)
            return {}

        out: Dict[str, PocketOptionRecord] = {}
        for pocket_id, payload in (raw or {}).items():
            try:
                record = PocketOptionRecord(
                    pocket_id=str(pocket_id),
                    registered_at=payload.get("registered_at"),
                    deposit_amount=float(payload.get("deposit_amount") or 0.0),
                    deposit_updated_at=payload.get("deposit_updated_at"),
                    last_seen=float(payload.get("last_seen") or time.time()),
                )
                out[record.pocket_id] = record
            except Exception as exc:
                log.warning("PocketOption store skipping invalid record %s: %s", pocket_id, exc)
        return out

    def _dump(self) -> Dict[str, Dict]:
        return {
            pid: {
                "registered_at": r.registered_at,
                "deposit_amount": r.deposit_amount,
                "deposit_updated_at": r.deposit_updated_at,
                "last_seen": r.last_seen,
            }
            for pid, r in self._records.items()
        }

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self._dump(), f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    def _ensure(self, pocket_id: str) -> PocketOptionRecord:
        record = self._records.get(pocket_id)
        if record:
            return record
        record = PocketOptionRecord(
            pocket_id=pocket_id,
            last_seen=time.time(),
        )
        self._records[pocket_id] = record
        return record

    def mark_registered(self, pocket_id: str, ts: Optional[float] = None) -> PocketOptionRecord:
        with self._lock:
            record = self._ensure(pocket_id)
            record.registered_at = ts or time.time()
            record.last_seen = time.time()
            self._save()
            return record

    def record_deposit(self, pocket_id: str, amount: float, ts: Optional[float] = None) -> PocketOptionRecord:
        with self._lock:
            record = self._ensure(pocket_id)
            if amount <= 0:
                return record
            if amount > record.deposit_amount:
                record.deposit_amount = amount
            record.deposit_updated_at = ts or time.time()
            record.last_seen = time.time()
            self._save()
            return record

    def get(self, pocket_id: str) -> Optional[PocketOptionRecord]:
        with self._lock:
            record = self._records.get(pocket_id)
            if record:
                return PocketOptionRecord(**asdict(record))
            return None
