import aiohttp
import logging
from typing import List, Optional

log = logging.getLogger(__name__)

API_V1 = "https://api.chart-img.com/v1/tradingview/advanced-chart"
API_V2 = "https://api.chart-img.com/v2/tradingview/advanced-chart"


def _normalize_interval(interval_min: int) -> str:
    if interval_min in (1, 3, 5, 15, 30):
        return f"{interval_min}m"
    if interval_min == 60:
        return "1h"
    return "5m"


async def fetch_advanced_chart(
    api_key: str,
    symbol: str,
    interval_min: int,
    studies: Optional[List[str]] = None,
    width: int = 900,
    height: int = 650,
    theme: str = "dark",
) -> Optional[bytes]:
    if not api_key:
        log.warning("[CHARTIMG] api_key EMPTY")
        return None

    interval = _normalize_interval(interval_min)

    # v1 query
    query = [
        ("symbol", symbol),
        ("interval", interval),
        ("width", str(int(width))),
        ("height", str(int(height))),
        ("theme", theme),
    ]
    if studies:
        for s in studies:
            s = (s or "").strip()
            if s:
                query.append(("studies", s))

    timeout = aiohttp.ClientTimeout(total=25)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # --- TRY #1: v1 + Bearer ---
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            async with session.get(API_V1, params=query, headers=headers) as resp:
                raw = await resp.read()
                if resp.status == 200 and raw:
                    log.info("[CHARTIMG] v1 bearer OK bytes=%s", len(raw))
                    return raw
                # логируем причину
                log.warning("[CHARTIMG] v1 bearer FAIL status=%s body=%s",
                            resp.status, raw[:300])
        except Exception as e:
            log.exception("[CHARTIMG] v1 bearer EXC: %s", e)

        # --- TRY #2: v1 + key in query (docs allow it) ---
        # https://api.chart-img.com/v1/tradingview/advanced-chart?...&key=YOUR_API_KEY  :contentReference[oaicite:2]{index=2}
        try:
            query2 = list(query) + [("key", api_key)]
            async with session.get(API_V1, params=query2) as resp:
                raw = await resp.read()
                if resp.status == 200 and raw:
                    log.info("[CHARTIMG] v1 key OK bytes=%s", len(raw))
                    return raw
                log.warning("[CHARTIMG] v1 key FAIL status=%s body=%s",
                            resp.status, raw[:300])
        except Exception as e:
            log.exception("[CHARTIMG] v1 key EXC: %s", e)

        # --- TRY #3: v2 POST + x-api-key (some keys/plans work only here) :contentReference[oaicite:3]{index=3}
        try:
            headers = {"x-api-key": api_key, "content-type": "application/json"}
            body = {
                "symbol": symbol,
                "interval": interval,
                "width": int(width),
                "height": int(height),
                "theme": theme,
            }
            if studies:
                # в v2 studies может ожидать другой формат, но часто принимает строки.
                body["studies"] = studies

            async with session.post(API_V2, headers=headers, json=body) as resp:
                raw = await resp.read()
                if resp.status == 200 and raw:
                    log.info("[CHARTIMG] v2 OK bytes=%s", len(raw))
                    return raw
                log.warning("[CHARTIMG] v2 FAIL status=%s body=%s",
                            resp.status, raw[:300])
        except Exception as e:
            log.exception("[CHARTIMG] v2 EXC: %s", e)

    return None
