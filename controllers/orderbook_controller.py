from typing import Optional, List
import datetime

from controllers.auth_controller import AuthController
from models.depth import DepthSnapshot
from models.order import Fill
from services.account_service import AccountService
from services.db_service import DBService
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
        balance_table: BalanceTable,
        db: DBService,
        auth: AuthController,
    ):
        self.md = md_service
        self.ob_table = orderbook_widget
        self.trades = trades_widget
        self.sim = sim
        self.account = account
        self.balance_table = balance_table
        self.db = db
        self.auth = auth
        self.last_depth: Optional[DepthSnapshot] = None

    # -------------------------------------------------
    # 시세 폴링 + 미체결 매칭
    # -------------------------------------------------
    def poll_and_render(self):
        try:
            snap = self.md.fetch_depth()  # 심볼 인자는 안 넘기는 쪽으로 단순화
        except TypeError:
            snap = self.md.fetch_depth()

        if not snap:
            return

        cur_sym = self.md.current_symbol() if hasattr(self.md, "current_symbol") else None
        prev_sym = getattr(self.last_depth, "symbol", None)
        snap_sym = getattr(snap, "symbol", cur_sym)

        # 심볼 변경 감지 시 초기화
        if prev_sym is not None and snap_sym is not None and prev_sym != snap_sym:
            self._reset_on_symbol_change()

        # 미체결 주문 매칭
        fills, snap2 = self.sim.match_working_on_depth(snap)
        self._append_fills_and_update_balance(fills)
        self._apply_depth(snap2)

    # -------------------------------------------------
    # 주문 핸들러
    # -------------------------------------------------
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

        # ✅ 남은 수량(미체결)이 있으면 DB에 주문 레코드 추가
        if remain > 0:
            self._record_working_order_to_db(
                side="SELL",
                price=price,
                qty=qty,
                remaining=remain,
            )

        return remain

    # ---- 심볼 변경 시 초기화 (MainWindow 에서 호출해도 OK) ----
    def on_symbol_changed(self, sym: str):
        self._reset_on_symbol_change()

    def _reset_on_symbol_change(self):
        self.last_depth = None

        # 시뮬레이터 대기주문 초기화
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

    # -------------------------------------------------
    # 호가 적용
    # -------------------------------------------------
    def _apply_depth(self, snap: DepthSnapshot):
        self.last_depth = snap
        self.ob_table.set_orderbook(snap.bids, snap.asks, snap.mid or 0.0)

    # -------------------------------------------------
    # 체결 처리 + 잔고 업데이트 + DB 기록
    # -------------------------------------------------
    def _append_fills_and_update_balance(self, fills: List[Fill]):
        if not fills:
            return

        # 로그인 유저 / 계좌 정보 준비 (DB 기록용)
        user_email = getattr(self.auth, "current_user", None)
        user_id = None
        account_id = None
        if user_email:
            user_id = self.db.get_user_id_by_email(user_email)
            if user_id is not None:
                account_id = self.db.get_primary_account_id(user_id)

        # 1) UI 체결표 + 2) AccountService + 3) DB(trades) + 4) DB(balance) 한 번에
        delta_cash = 0.0
        exchange = getattr(self.md, "provider", "MOCK")
        symbol = self.md.current_symbol() if hasattr(self.md, "current_symbol") else ""

        for f in fills:
            # 1) UI 체결표: TradesTable.add_fill 사용
            self.trades.add_fill(f.side, f.price, f.qty)

            # 2) 현금 변화 (시뮬레이션 계좌)
            notional = float(f.price) * int(f.qty)
            if f.side.upper() == "SELL":
                delta_cash += notional
            else:  # BUY
                delta_cash -= notional

            # 3) DB 체결 기록
            if user_id is not None and account_id is not None:
                self.db.insert_trade(
                    user_id=user_id,
                    account_id=account_id,
                    symbol=symbol or f.symbol,
                    side=f.side.upper(),
                    price=float(f.price),
                    qty=float(f.qty),
                    exchange=exchange,
                    remark=None,
                )

        # 4) 시뮬레이션 계좌에 반영 + 잔고 테이블 업데이트
        if delta_cash != 0.0:
            self.account.apply_cash(delta_cash)
            self.balance_table.render(self.account.state)

            # DB 계좌 잔액 업데이트
            if account_id is not None:
                self.db.update_balance(account_id, delta_cash)

    def _record_working_order_to_db(self, side: str, price: float, qty: float, remaining: float):
        """미체결 주문을 orders 테이블에 기록"""
        # 로그인한 사용자/계좌 확인
        user_email = getattr(self.auth, "current_user", None)
        if not user_email:
            print("[OrderBookController] _record_working_order_to_db: not logged in")
            return

        user_id = self.db.get_user_id_by_email(user_email)
        if user_id is None:
            print("[OrderBookController] _record_working_order_to_db: user not found in DB")
            return

        account_id = self.db.get_primary_account_id(user_id)
        if account_id is None:
            print("[OrderBookController] _record_working_order_to_db: no account for user")
            return

        symbol = self.md.current_symbol() if hasattr(self.md, "current_symbol") else ""

        order_id = self.db.insert_order(
            user_id=user_id,
            account_id=account_id,
            symbol=symbol,
            side=side.upper(),
            price=float(price),
            qty=float(qty),
            remaining_qty=float(remaining),
            status="WORKING",
        )

        # (선택) 시뮬레이터 미체결 객체에 DB order_id를 태워둘 수도 있음
        # 예: sim.working[-1].db_order_id = order_id
        if order_id is not None and hasattr(self.sim, "working") and self.sim.working:
            try:
                # 가장 최근에 추가된 대기 주문이 방금 주문이라고 가정
                last_working = self.sim.working[-1]
                setattr(last_working, "db_order_id", order_id)
            except Exception as e:
                print("[OrderBookController] attach db_order_id to working err:", e)
