import logging
from bot.config import settings
from .stub import StubAnalyzer

log = logging.getLogger(__name__)

def _build_analyzer():
    backend = (settings.analyzer_backend or "stub").strip().lower()
    log.info("Analyzer backend from settings: %s", backend)

    if backend == "tradingview":
        try:
            from .tradingview import TradingViewAnalyzer
            log.info("TradingViewAnalyzer enabled")
            return TradingViewAnalyzer()
        except Exception as e:
            log.exception("TradingViewAnalyzer init failed, fallback to StubAnalyzer: %s", e)
            return StubAnalyzer()

    log.info("StubAnalyzer enabled")
    return StubAnalyzer()

analyzer = _build_analyzer()
