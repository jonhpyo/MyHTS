# adapters/base.py
from abc import ABC, abstractmethod
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class Bar:
    ts: int
    o: float; h: float; l: float; c: float; v: float

class MarketDataSource(ABC):
    @abstractmethod
    def get_recent_bars(self, symbol: str, timeframe: str, limit: int) -> List[Bar]:
        ...
    @abstractmethod
    def get_last_trade(self, symbol: str) -> Tuple[int, float, int]:
        ...
