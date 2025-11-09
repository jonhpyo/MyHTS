from dataclasses import dataclass
from typing import Literal

Side = Literal["BUY", "SELL"]

@dataclass
class Side:
    side: Literal["BUY", "SELL"]
    price: float
    id: int | None  # 내부 ID (simulator나 DB order_id 등)
    side: Side  # BUY / SELL
    price: float  # 지정가
    qty: int  # 총 주문 수량
    remaining: int  # 남은 수량 (미체결 잔량)
    type: Literal["LMT"] = "LMT"  # 현재는 지정가 주문만 지원
    db_order_id: int | None = None  # DB에 저장된 주문 ID (optional)
    created_at: float | None = None  # time.time() 저장용 (optional)

@dataclass
class Fill:
    side: Side
    price: float
    qty: int
