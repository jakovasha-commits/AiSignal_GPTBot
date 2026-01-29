import json
from pathlib import Path
from threading import Lock

from bot.config import settings


class ApprovedStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._lock = Lock()
        self._approved: set[int] = set()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                self._approved = {int(uid) for uid in raw if str(uid).isdigit()}
        except Exception:
            self._approved = set()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(sorted(self._approved), f, ensure_ascii=False, indent=2)

    def add(self, chat_id: int) -> None:
        with self._lock:
            if chat_id in self._approved:
                return
            self._approved.add(chat_id)
            self._save()

    def contains(self, chat_id: int) -> bool:
        with self._lock:
            return chat_id in self._approved


approved_store = ApprovedStore(settings.approved_store_path)
