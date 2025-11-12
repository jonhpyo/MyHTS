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
        use_local_exchange: bool = False,
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
        self.use_local_exchange = use_local_exchange

    # -------------------------------------------------
    # 시세 폴링 + 미체결 매칭
    # -------------------------------------------------
    # -------------------------------------------------
    # 시세 폴링 + 미체결 매칭 + 로컬 잔량 덮어쓰기
    # -------------------------------------------------
    def poll_and_render(self):
        # 1) 시세는 그냥 가져와서 화면에 보여줄 기준으로 사용
        try:
            snap = self.md.fetch_depth()
        except TypeError:
            snap = self.md.fetch_depth()

        if not snap:
            return

        cur_sym = self.md.current_symbol() if hasattr(self.md, "current_symbol") else None
        prev_sym = getattr(self.last_depth, "symbol", None)
        snap_sym = getattr(snap, "symbol", cur_sym)

        if prev_sym is not None and snap_sym is not None and prev_sym != snap_sym:
            self._reset_on_symbol_change()

        symbol = snap_sym or cur_sym or ""
        symbol_upper = symbol.upper()

        if self.use_local_exchange:
            # 🔹 로컬 거래소 모드: 시뮬레이터 X, DB 오더북만 반영

            # 1) DB에서 로컬 오더북 집계
            if symbol_upper:
                try:
                    local_ob = self.db.get_local_orderbook(symbol_upper)
                except Exception as e:
                    print("[OrderBookController] get_local_orderbook error:", e)
                    local_ob = None
            else:
                local_ob = None

            # 2) 외부 호가 스냅샷에 로컬 잔량/건수 덮어쓰기
            if local_ob:
                bids_map = local_ob.get("bids", {})
                asks_map = local_ob.get("asks", {})

                new_bids = []
                for price, _orig_qty, _level in snap.bids:
                    local = bids_map.get(float(price))
                    qty = local["qty"] if local else 0.0
                    cnt = local["cnt"] if local else 0  # ✅ DB 집계 건수
                    new_bids.append((price, qty, cnt))  # ✅ 3번째 값을 cnt로

                new_asks = []
                for price, _orig_qty, _level in snap.asks:
                    local = asks_map.get(float(price))
                    qty = local["qty"] if local else 0.0
                    cnt = local["cnt"] if local else 0
                    new_asks.append((price, qty, cnt))

                snap.bids = new_bids
                snap.asks = new_asks

            # 3) 오더북 UI 반영
            self._apply_depth(snap)

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

    def buy_limit(self, price: float, qty: int) -> int:
        """
        지정가 매수:
        - 시뮬레이터 기준으로 지금 호가에서 바로 체결될 부분은 체결
        - 남는 수량이 있으면 DB에 미체결 주문(WORKING)으로 기록
        """
        if not self.last_depth:
            return qty

        # 시뮬레이터에 위임 (sell_limit 과 대칭 메서드가 있다고 가정)
        fills, new_depth, remain = self.sim.buy_limit_now_or_queue(price, qty, self.last_depth)

        # 체결분 처리 (체결 테이블 + 잔고 반영)
        self._append_fills_and_update_balance(fills)

        # 오더북 갱신
        self._apply_depth(new_depth)

        # 남은 수량이 있으면 미체결 주문으로 DB에 기록
        if remain > 0:
            self._record_working_order_to_db(
                side="BUY",
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

        # 🔹 1) mid 가격 기준으로 평가금액/미실현손익 갱신
        try:
            mid = snap.mid or 0.0
        except Exception:
            mid = 0.0

        if mid and hasattr(self.account, "mark_to_market"):
            self.account.mark_to_market(mid)

        # 🔹 2) 잔고 요약/포지션 테이블 재렌더
        self.balance_table.render(self.account.state)

    # -------------------------------------------------
    # 체결 처리 + 잔고 업데이트 + DB 기록
    # -------------------------------------------------
    def _append_fills_and_update_balance(self, fills: List[Fill]):
        """체결 리스트를 UI/시뮬 계좌/DB(잔고)에 반영"""
        if not fills:
            return

        # 로그인 유저 / 계좌 정보 (잔고 업데이트용)
        user_email = getattr(self.auth, "current_user", None)
        user_id = None
        account_id = None
        if user_email:
            user_id = self.db.get_user_id_by_email(user_email)
            if user_id is not None:
                account_id = self.db.get_primary_account_id(user_id)

        delta_cash = 0.0
        symbol = self.md.current_symbol() if hasattr(self.md, "current_symbol") else ""

        for f in fills:
            # ---- 1) side 를 문자열로 정규화 (Enum / str 모두 지원) ----
            if hasattr(f.side, "Side"):          # Enum (Side.BUY / Side.SELL)
                side_str = f.side.side.upper()
            else:                                # 이미 str 이라면
                side_str = str(f.side.side).upper()

            # ---- 2) UI 체결표에 반영 ----
            # TradesTable.add_fill(side: str, price: float, qty: int)
            self.trades.add_fill(side_str, float(f.price), int(f.qty))

            # ---- 3) 시뮬레이션 계좌 현금 변화 ----
            notional = float(f.price) * float(f.qty)
            if side_str == "SELL":
                delta_cash += notional
            else:  # BUY
                delta_cash -= notional

            # ⚠️ 지금은 trades 테이블 구조가 buy_order_id/sell_order_id 기반이라
            # 여기에서 직접 trades 에 INSERT 하지는 않는다.
            # 실제 로컬 거래소 모드에서는 매칭 엔진이 orders → trades 를 기록하고,
            # 클라이언트는 그걸 읽어서 화면에 그리는 쪽이 자연스럽다.

        # ---- 4) 시뮬레이션 계좌 + 잔고 테이블 갱신 ----
        if delta_cash != 0.0:
            # 메모리 상 계좌
            self.account.apply_cash(delta_cash)
            self.balance_table.render(self.account.state)

            # DB accounts 잔고도 테스트/로그용으로 반영
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
