# services/account_service.py
from dataclasses import dataclass
from typing import Iterable
from models.order import Fill

@dataclass
class AccountState:
    cash: float = 0.0        # 단순 현금 (SELL:+ / BUY:-)
    position: int = 0        # 보유 수량(+ 롱, - 숏)
    avg_price: float = 0.0   # 단가(선택)

    last_price: float = 0.0    # 최근 시세
    asset_value: float = 0.0   # 평가금액 = position * last_price
    realized_pnl: float = 0.0  # 실현손익
    unrealized_pnl: float = 0.0# 미실현손익

class AccountService:
    def __init__(self, initial_cash: float = 0.0):
        self.state = AccountState(cash=initial_cash)

    def apply_cash(self, delta: float):
        self.state.cash += delta

    # services/account_service.py 안

    def apply_fill(self, f: Fill):
        """
        체결 1건이 들어올 때마다
          - cash
          - position
          - avg_price
          - realized_pnl
        를 갱신하는 함수 (단일 심볼, 롱 포지션 기준)
        """
        side = f.side.upper()
        price = float(f.price)
        qty = int(f.qty)

        # 1) 현금 변화
        notional = price * qty
        if side == "SELL":
            self.state.cash += notional
        else:  # BUY
            self.state.cash -= notional

        # 2) 포지션/평균단가/실현손익
        pos = self.state.position
        avg = self.state.avg_price

        if side == "BUY":
            # 매수: 새 평균단가 = (기존포지션*기존평단 + 신규수량*가격) / (합산수량)
            new_pos = pos + qty
            if new_pos > 0:
                self.state.avg_price = ((pos * avg) + (qty * price)) / new_pos
            else:
                self.state.avg_price = 0.0
            self.state.position = new_pos

        elif side == "SELL":
            # 매도: 보유수량 줄이고, 그만큼 실현손익 반영
            sell_qty = min(qty, pos)  # 보유수량 초과 매도 방지용 (단순 안전장치)
            if sell_qty > 0:
                self.state.realized_pnl += (price - avg) * sell_qty

            self.state.position = pos - qty
            # 포지션이 0 되면 평균단가 초기화
            if self.state.position <= 0:
                self.state.avg_price = 0.0

    def mark_to_market(self, last_price: float):
        self.state.last_price = float(last_price)
        self.state.asset_value = self.state.position * self.state.last_price
        if self.state.position != 0:
            self.state.unrealized_pnl = (self.state.last_price - self.state.avg_price) * self.state.position
        else:
            self.state.unrealized_pnl = 0.0


    def apply_fills(self, fills: Iterable[Fill]):
        for f in fills:
            self.apply_fill(f)

    def apply_cash(self, delta: float):
        self.state.cash = float(self.state.cash) + float(delta)
