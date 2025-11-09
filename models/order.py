from dataclasses import dataclass
from typing import Optional, Literal

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
    side: Side  # BUY / SELL
    price: float  # 체결 가격
    qty: float  # 체결 수량 (DB numeric(18,6) 이라 float 쪽이 낫다)

    # 🔽 DB/매칭용 메타데이터 (옵셔널)
    order_id: Optional[int] = None  # 이 체결이 속한 주문 ID (orders.id)
    symbol: Optional[str] = None  # 종목 코드 (예: "SOLUSDT")
    user_id: Optional[int] = None  # 체결된 쪽 유저 ID (원하면 사용)
    account_id: Optional[int] = None  # 계좌 ID
