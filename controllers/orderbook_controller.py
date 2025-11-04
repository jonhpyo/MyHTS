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
        # ⬇️ 현재 심볼을 명시적으로 요청(서비스 구현에 따라 필요 없으면 인자 제거)
        cur_sym = self.md.current_symbol() if hasattr(self.md, "current_symbol") else None
        try:
            snap = self.md.fetch_depth(cur_sym) if cur_sym is not None else self.md.fetch_depth()
        except TypeError:
            # fetch_depth(symbol) 시그니처가 없으면 무시하고 호출
            snap = self.md.fetch_depth()

        if not snap:
            return

        # ⬇️ 심볼 변경 감지: 스냅샷이 들고 있는 symbol 과 last_depth 의 symbol 이 다르면 초기화
        prev_sym = getattr(self.last_depth, "symbol", None)
        snap_sym = getattr(snap, "symbol", cur_sym)
        if prev_sym is not None and snap_sym is not None and prev_sym != snap_sym:
            self._reset_on_symbol_change()

        # 미체결 매칭
        fills, snap2 = self.sim.match_working_on_depth(snap)
        self._append_fills_and_update_balance(fills)
        self._apply_depth(snap2)

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
        self._append_fills_and_update_balance(fills)
        self._apply_depth(new_depth)

    def sell_limit(self, price: float, qty: int) -> int:
        if not self.last_depth:
            return qty
        fills, new_depth, remain = self.sim.sell_limit_now_or_queue(price, qty, self.last_depth)
        self._append_fills_and_update_balance(fills)
        self._apply_depth(new_depth)
        return remain

    # ---- 심볼 변경 시 초기화 훅 (MainWindow 에서 호출해도 OK) ----
    def on_symbol_changed(self, sym: str):
        self._reset_on_symbol_change()

    # ---- 내부 유틸 ----
    def _reset_on_symbol_change(self):
        # 컨트롤러 상태
        self.last_depth = None
        # 시뮬레이터 대기 주문/버퍼 비우기
        if hasattr(self.sim, "cancel_all"):
            self.sim.cancel_all()
        elif hasattr(self.sim, "working"):
            try:
                self.sim.working.clear()
            except Exception:
                self.sim.working = []
        # 체결표 초기화
        try:
            self.trades.trades.clear()
            self.trades._render()
        except Exception:
            pass
        # 오더북 비우기
        try:
            self.ob_table.set_orderbook([], [], 0.0)
        except Exception:
            pass

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
