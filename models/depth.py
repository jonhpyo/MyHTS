from dataclasses import dataclass
from typing import List, Tuple, Optional

# (price, size, level)
Level = Tuple[float, int, int]

@dataclass
class DepthSnapshot:
    bids: List[Level]
    asks: List[Level]
    mid: Optional[float] = None
    symbol: Optional[str] = None  # ⬅️ 추가

    @staticmethod
    def calc_mid(bids: List[Level], asks: List[Level]) -> Optional[float]:
        bb = next((p for p, q, _ in bids if q > 0), None)
        ba = next((p for p, q, _ in asks if q > 0), None)
        if bb is not None and ba is not None:
            return (bb + ba) / 2.0
        return bb or ba
