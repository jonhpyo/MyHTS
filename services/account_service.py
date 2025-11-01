# services/account_service.py
from dataclasses import dataclass
from typing import Iterable
from models.order import Fill

@dataclass
class AccountState:
    cash: float = 0.0        # 단순 현금 (SELL:+ / BUY:-)
    position: int = 0        # 보유 수량(+ 롱, - 숏)
    avg_price: float = 0.0   # 단가(선택)

class AccountService:
    def __init__(self, initial_cash: float = 0.0):
        self.state = AccountState(cash=initial_cash)

    def apply_fill(self, f: Fill):
        # 현금
        if f.side.upper() == "SELL":
            self.state.cash += float(f.price) * int(f.qty)
            self.state.position -= int(f.qty)
        else:  # BUY
            self.state.cash -= float(f.price) * int(f.qty)
            self.state.position += int(f.qty)

        # (선택) 평균단가 업데이트 – 아주 단순화(포지션 절대값 증가 시에만 반영)
        # 필요 없으면 이 블록 통째로 제거 가능
        pos = self.state.position
        if pos != 0:
            # 단순 이동평균 느낌으로 유지(엄밀한 실현/미실현PnL은 별도 로직 필요)
            w = min(abs(pos), int(f.qty))
            if w > 0:
                # 새 avg를 최근 체결가 쪽으로 조금 이동 (가벼운 추정치)
                self.state.avg_price = (self.state.avg_price * 0.7) + (float(f.price) * 0.3)

    def apply_fills(self, fills: Iterable[Fill]):
        for f in fills:
            self.apply_fill(f)

    def apply_cash(self, delta: float):
        self.state.cash = float(self.state.cash) + float(delta)
