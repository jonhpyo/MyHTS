# models/working_order.py
from dataclasses import dataclass, field
from typing import Literal, Optional
import time

from models.order import Side  # 이미 BUY / SELL enum 있다고 가정


@dataclass
class WorkingOrder:
    """미체결 주문(지정가 등)을 표현하는 데이터 클래스"""
    id: int                      # 시뮬레이터 내부 주문 ID
    side: Side                   # BUY / SELL
    price: float                 # 주문 가격
    qty: int                     # 총 주문 수량
    remaining: int               # 미체결 잔량
    type: Literal["LMT"] = "LMT" # 주문 타입 (지정가)
    created_at: float = field(default_factory=time.time)

    # DB 연동용 필드 (선택)
    db_order_id: Optional[int] = None
