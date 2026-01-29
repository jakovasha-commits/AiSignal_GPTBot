import json
from pathlib import Path
from threading import Lock

from bot.config import settings


class UserStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._lock = Lock()
        self._users: set[int] = set()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                self._users = {int(uid) for uid in raw if str(uid).isdigit()}
        except Exception:
            self._users = set()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(sorted(self._users), f, ensure_ascii=False, indent=2)

    def add(self, chat_id: int) -> None:
        if chat_id in settings.admin_ids:
            return
        with self._lock:
            if chat_id in self._users:
                return
            self._users.add(chat_id)
            self._save()

    def list(self) -> list[int]:
        with self._lock:
            return list(self._users)


user_store = UserStore(settings.user_store_path)
