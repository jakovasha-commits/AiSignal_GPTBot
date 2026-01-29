from dataclasses import dataclass, field
from typing import Optional, List, Tuple

@dataclass
class AnalysisResult:
    trend: str                 # "UP" or "DOWN"
    win_prob_min: int
    win_prob_max: int
    reversal_prob_min: int
    reversal_prob_max: int
    volatility: int            # 0..100
    wait_seconds: int = 15

    # Доп. строка, которую можно вставить в сообщение без ломки шаблона
    # (например: точка входа / SL / TP)
    entry_sl_tp: str = ""

    # --- Поля для формата "screenshot" (как на примере) ---
    signal_action: str = ""  # "ПОКУПКА" | "ПРОДАЖА"
    signal_interval_min: int = 0
    # список строк вида ("RSI", "28") -> будет печататься как "GPT: RSI 28"
    signal_indicators: List[Tuple[str, str]] = field(default_factory=list)
    bull_bear_strength: float = 0.0
    chart_image_bytes: Optional[bytes] = None
