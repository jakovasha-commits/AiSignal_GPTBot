from datetime import datetime, time
from zoneinfo import ZoneInfo


MSK = ZoneInfo("Europe/Moscow")


def is_market_open_msk(now: datetime | None = None) -> bool:
    now = now or datetime.now(MSK)
    t = now.time()
    return time(8, 0) <= t <= time(23, 0)
