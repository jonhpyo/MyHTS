from typing import Optional, List, Dict
from models.depth import DepthSnapshot
from services.marketdata_service import MarketDataService
from services.order_simulator import OrderSimulator
from widgets.orderbook_table import OrderBookTable
from widgets.trades_table import TradesTable
from models.order import Fill

class OrderBookController:
    """서비스↔ui 연결. 타이머에서 주기적으로 fetch→ui 갱신, 주문 이벤트 처리."""
    def __init__(self, md: MarketDataService, ob_table: OrderBookTable, trades: TradesTable):
        self.md = md
        self.ob_table = ob_table
        self.trades = trades
        self.sim = OrderSimulator()
        self.last_depth: Optional[DepthSnapshot] = None

    def poll_and_render(self):
        snap = self.md.fetch_depth()
        if not snap:
            return
        # 미체결 매칭
        fills, snap2 = self.sim.match_working_on_depth(snap)
        self._append_fills(fills)
        self.last_depth = snap2
        self.ob_table.set_orderbook(bids=snap2.bids, asks=snap2.asks, mid_price=snap2.mid or 0.0)

    # ---- 주문 핸들러 ----
    def sell_market(self, qty: int):
        if not self.last_depth: return
        fills, new_depth = self.sim.sell_market(qty, self.last_depth)
        self._append_fills(fills)
        self._apply_depth(new_depth)

    def buy_market(self, qty: int):
        if not self.last_depth: return
        fills, new_depth = self.sim.buy_market(qty, self.last_depth)
        self._append_fills(fills)
        self._apply_depth(new_depth)

    def sell_limit(self, price: float, qty: int) -> int:
        if not self.last_depth: return qty
        fills, new_depth, remain = self.sim.sell_limit_now_or_queue(price, qty, self.last_depth)
        self._append_fills(fills)
        self._apply_depth(new_depth)
        return remain

    # ---- 내부 유틸 ----
    def _apply_depth(self, snap: DepthSnapshot):
        self.last_depth = snap
        self.ob_table.set_orderbook(snap.bids, snap.asks, snap.mid or 0.0)

    def _append_fills(self, fills: List[Fill]):
        for f in fills:
            up = (f.side == "BUY")  # BUY 녹색/SELL 파랑 등 원하는 규칙에 맞춰 조정
            self.trades.trades.insert(0, {"time": "", "price": round(f.price, 2), "qty": int(f.qty), "up": up})
        if fills:
            self.trades.trades = self.trades.trades[: self.trades.max_rows]
            self.trades._render()
