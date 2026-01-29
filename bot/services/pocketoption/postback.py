from __future__ import annotations

import logging
from typing import Any, Dict

from aiohttp import web

from bot.config import settings
from bot.services.pocketoption.store import PocketOptionStore

log = logging.getLogger(__name__)


class PostbackServer:
    """Минимальный HTTP-приёмник, который PocketOption сможет вызвать POST/GET с данными регистрации/депозита."""

    def __init__(self):
        self.store = PocketOptionStore(settings.pocketoption_store_path)
        self.secret = settings.pocketoption_postback_secret

    async def handler(self, request: web.Request) -> web.Response:
        token = request.query.get("token") or request.headers.get("X-PO-Token")
        if not token or token != self.secret:
            log.warning("PocketOption postback rejected wrong token=%s", token)
            raise web.HTTPForbidden(text="invalid token")

        payload = await _safe_payload(request)
        pocket_id = str(payload.get("pocket_id") or payload.get("user_id") or "").strip()
        if not pocket_id:
            raise web.HTTPBadRequest(text="missing pocket_id")

        event = (payload.get("event") or payload.get("type") or "").lower()
        deposit_value = payload.get("deposit") or payload.get("deposit_amount") or payload.get("amount")

        if event == "registration":
            self.store.mark_registered(pocket_id)
            log.info("PocketOption registration confirmed for %s", pocket_id)
        elif event == "deposit":
            amount = _safe_float(deposit_value)
            if amount:
                self.store.record_deposit(pocket_id, amount)
                log.info("PocketOption deposit recorded for %s amount=%.2f", pocket_id, amount)
        else:
            log.info("PocketOption postback got unknown event=%s payload=%s", event, payload)

        return web.json_response({"ok": True})


async def _safe_payload(request: web.Request) -> Dict[str, Any]:
    try:
        if request.content_type and "json" in request.content_type:
            return await request.json()
        data = await request.post()
        return dict(data or {})
    except Exception:
        return dict(request.rel_url.query)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def create_app() -> web.Application:
    server = PostbackServer()
    app = web.Application()
    path = settings.pocketoption_postback_path or "/pocketoption/postback"
    app.router.add_post(path, server.handler)
    app.router.add_get(path, server.handler)
    return app


def run() -> None:
    port = int(settings.pocketoption_postback_port or 9009)
    web.run_app(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()
