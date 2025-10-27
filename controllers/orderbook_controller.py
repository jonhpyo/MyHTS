from typing import Optional, List, Dict
from models.depth import DepthSnapshot
from services.marketdata_service import MarketDataService
from services.order_simulator import OrderSimulator
from widgets.orderbook_table import OrderBookTable
from widgets.trades_table import TradesTable
from models.order import Fill
import datetime

class OrderBookController:
    """서비스↔ui 연결. 타이머에서 주기적으로 fetch→ui 갱신, 주문 이벤트 처리."""
    def __init__(self, md_service, orderbook_widget, trades_widget, sim, balance_view):
        self.md = md_service
        self.ob_table = orderbook_widget
        self.trades = trades_widget
        self.sim = sim
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
        """체결들을 TradesTable에 반영."""
        if not fills:
            return
        for f in fills:
            # TradesTable.add_fill(side, price, qty) 사용 (굵게/색상/배경 처리 포함)
            self.trades.add_fill(f.side, f.price, f.qty)
