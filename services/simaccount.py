# accounts.py
from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class PositionState:
    """
    심볼 하나에 대한 포지션 상태
    """
    position: float = 0.0       # 보유 수량(+롱, -숏)
    avg_price: float = 0.0      # 평균 단가

    last_price: float = 0.0     # 최근 시세
    asset_value: float = 0.0    # 평가금액 = position * last_price
    realized_pnl: float = 0.0   # 실현손익
    unrealized_pnl: float = 0.0 # 미실현손익


class SimAccount:
    """
    멀티 심볼 시뮬 계좌
    """

    def __init__(self):
        self.cash: float = 0.0
        self.positions: Dict[str, PositionState] = {}
        self.total_unrealized: float = 0.0

    # ============================================================
    # 🔥 여기! _get_or_create_position 추가했다
    # ============================================================
    def _get_or_create_position(self, symbol: str) -> PositionState:
        """
        해당 symbol의 포지션이 없으면 생성해서 반환
        """
        if symbol not in self.positions:
            self.positions[symbol] = PositionState()
        return self.positions[symbol]

    # ============================================================
    # 계좌 현금 적용
    # ============================================================
    def apply_cash(self, delta: float):
        self.cash += float(delta)

    # ============================================================
    # 체결 반영 (멀티 심볼 대응)
    # ============================================================
    def apply_fill(self, symbol: str, side: str, price: float, qty: float):
        """
        체결 1건을 계좌에 반영.
        BUY = 포지션 증가
        SELL = 포지션 감소
        """
        symbol = str(symbol)
        side = side.upper()
        price = float(price)
        qty = float(qty)

        pos = self._get_or_create_position(symbol)

        old_pos = pos.position
        old_avg = pos.avg_price

        # --------------------------------
        # BUY 체결
        # --------------------------------
        if side == "BUY":
            new_pos = old_pos + qty

            if old_pos >= 0:
                # 롱 포지션 증가
                total_cost = old_pos * old_avg + qty * price
                pos.avg_price = total_cost / new_pos if new_pos != 0 else 0.0
            else:
                # 숏 청산 또는 반전
                closed_qty = min(abs(old_pos), qty)
                realized = (old_avg - price) * closed_qty
                pos.realized_pnl += realized

                if new_pos > 0:
                    # 숏 완전 청산 후 롱 반전
                    pos.avg_price = price

            pos.position = new_pos

        # --------------------------------
        # SELL 체결
        # --------------------------------
        else:  # SELL
            new_pos = old_pos - qty

            if old_pos <= 0:
                # 숏 포지션 증가
                total_cost = old_pos * old_avg - qty * price
                pos.avg_price = total_cost / new_pos if new_pos != 0 else 0.0
            else:
                # 롱 청산 또는 반전
                closed_qty = min(abs(old_pos), qty)
                realized = (price - old_avg) * closed_qty
                pos.realized_pnl += realized

                if new_pos < 0:
                    # 롱 완전 청산 후 숏 반전
                    pos.avg_price = price

            pos.position = new_pos

    # ============================================================
    # 마크투마켓 (현재가 dict 기반)
    # ============================================================
    def mark_to_market(self, prices: Dict[str, float]):
        total_unrealized = 0.0

        for sym, pos in self.positions.items():
            last = float(prices.get(sym, pos.last_price or pos.avg_price))
            pos.last_price = last

            pos.asset_value = pos.position * last
            pos.unrealized_pnl = (last - pos.avg_price) * pos.position

            total_unrealized += pos.unrealized_pnl

        self.total_unrealized = total_unrealized

    # ============================================================
    # ui/DB용 구조 변환
    # ============================================================
    @property
    def state(self) -> Dict[str, Any]:
        position_list = []

        for sym, pos in self.positions.items():
            position_list.append({
                "symbol": sym,
                "qty": pos.position,
                "avg_price": pos.avg_price,
                "last_price": pos.last_price,
                "asset_value": pos.asset_value,
                "realized_pnl": pos.realized_pnl,
                "unrealized_pnl": pos.unrealized_pnl,
            })

        return {
            "cash": self.cash,
            "positions": position_list
        }
