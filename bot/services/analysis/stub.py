import random
from .models import AnalysisResult
from .fibo_hints import fibo_template


class StubAnalyzer:
    async def analyze(self, pair: str, otc: bool, expiry_min: int) -> AnalysisResult:
        # Заглушка: имитируем результат (не реальная торговая рекомендация)
        trend = random.choice(["UP", "DOWN"])
        win_min, win_max = (70, 73) if trend == "UP" else (68, 72)
        rev_min, rev_max = (43, 49)
        vol = random.randint(30, 55)
        return AnalysisResult(
            trend=trend,
            win_prob_min=win_min,
            win_prob_max=win_max,
            reversal_prob_min=rev_min,
            reversal_prob_max=rev_max,
            volatility=vol,
            wait_seconds=15,
            entry_sl_tp=fibo_template(trend)
        )
