from typing import Optional, List
import datetime

from models.depth import DepthSnapshot
from models.order import Fill
from services.account_service import AccountService
from services.marketdata_service import MarketDataService
from services.order_simulator import OrderSimulator
from widgets.balance_table import BalanceTable
from widgets.orderbook_table import OrderBookTable
from widgets.trades_table import TradesTable


class OrderBookController:
    """서비스↔UI 연결. 타이머에서 주기적으로 fetch→UI 갱신, 주문 이벤트 처리."""
    def __init__(
        self,
        md_service: MarketDataService,
        orderbook_widget: OrderBookTable,
        trades_widget: TradesTable,
        sim: OrderSimulator,
        account: AccountService,
        balance_table: BalanceTable
    ):
        self.md = md_service
        self.ob_table = orderbook_widget
        self.trades = trades_widget
        self.sim = sim
        self.account = account
        self.balance_table = balance_table
        self.last_depth: Optional[DepthSnapshot] = None

    def poll_and_render(self):
        snap = self.md.fetch_depth()
        if not snap:
            return
        # 미체결 매칭
        fills, snap2 = self.sim.match_working_on_depth(snap)
        self._append_fills_and_update_balance(fills)
        self.last_depth = snap2
        self.ob_table.set_orderbook(
            bids=snap2.bids, asks=snap2.asks, mid_price=snap2.mid or 0.0
        )

    # ---- 주문 핸들러 ----
    def sell_market(self, qty: int):
        if not self.last_depth:
            return
        fills, new_depth = self.sim.sell_market(qty, self.last_depth)
        self._append_fills_and_update_balance(fills)
        self._apply_depth(new_depth)

    def buy_market(self, qty: int):
        if not self.last_depth:
            return
        fills, new_depth = self.sim.buy_market(qty, self.last_depth)
        # ⬇️ 잔고까지 갱신하는 함수로 교체
        self._append_fills_and_update_balance(fills)
        self._apply_depth(new_depth)

    def sell_limit(self, price: float, qty: int) -> int:
        if not self.last_depth:
            return qty
        fills, new_depth, remain = self.sim.sell_limit_now_or_queue(price, qty, self.last_depth)
        # ⬇️ 잔고까지 갱신하는 함수로 교체
        self._append_fills_and_update_balance(fills)
        self._apply_depth(new_depth)
        return remain

    # ---- 내부 유틸 ----
    def _apply_depth(self, snap: DepthSnapshot):
        self.last_depth = snap
        self.ob_table.set_orderbook(snap.bids, snap.asks, snap.mid or 0.0)

    def _append_fills_and_update_balance(self, fills: List[Fill]):
        if not fills:
            return

        # 1) 체결 테이블 반영
        for f in fills:
            now = datetime.datetime.now().strftime("%H:%M:%S")
            up = (f.side == "SELL")  # 색상 규칙
            self.trades.trades.insert(0, {
                "time": now,
                "price": round(f.price, 2),
                "qty": int(f.qty),
                "up": up
            })
        self.trades.trades = self.trades.trades[: self.trades.max_rows]
        self.trades._render()

        # 2) 잔고(현금) 갱신: SELL = +, BUY = -
        delta_cash = 0.0
        for f in fills:
            notional = float(f.price) * int(f.qty)
            if f.side.upper() == "SELL":
                delta_cash += notional
            else:  # BUY
                delta_cash -= notional
        self.account.apply_cash(delta_cash)

        # 3) 잔고 표시 갱신
        self.balance_table.render(self.account.state)
