from dataclasses import dataclass
from typing import Literal

Side = Literal["BUY", "SELL"]

@dataclass
class WorkingOrder:
    side: Side
    price: float
    qty: int
    type: Literal["LMT"]

@dataclass
class Fill:
    side: Side
    price: float
    qty: int
