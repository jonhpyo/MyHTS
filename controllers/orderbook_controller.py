from typing import Optional, List, Any
from controllers.auth_controller import AuthController
from models.depth import DepthSnapshot
from models.order import Fill
from services.simaccount import SimAccount
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
        account: SimAccount,
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

    def init_account_ui(self):
        user_id, account_id = self._get_current_user_and_account_id()
        if user_id is None or account_id is None:
            return

        # DB → SimAccount → BalanceTable
        self._refresh_balance_table_from_db(account_id)

        # 처음 depth 스냅샷도 있으면 적용
        try:
            snap = self.md.fetch_depth()
            if snap:
                self._apply_depth(snap)
        except Exception:
            pass
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
        # 로컬 거래소(매칭엔진) 모드에서만 동작
        if not getattr(self, "use_local_exchange", False):
            return

        user_id, account_id = self._get_current_user_and_account_id()
        if user_id is None or account_id is None:
            return

        symbol = self.md.current_symbol() if hasattr(self.md, "current_symbol") else ""
        if not symbol:
            return

        # 1) DB에서 시장가 매도 실행 (IOC)
        res = self.db.place_market_sell(user_id, account_id, symbol, qty, ioc=True)

        # 2) 체결 리스트
        fills = res.get("fills") or res.get("trades") or []

        # 3) 체결/잔고테이블 갱신
        self._append_fills_and_update_balance(account_id, fills)

        # 4) 호가/오더북 갱신
        try:
            snap = self.md.fetch_depth()
            if snap:
                self._apply_depth(snap)
        except Exception:
            pass

    def buy_market(self, qty: int):
        # 로컬 거래소(매칭엔진) 모드에서만 동작
        if not getattr(self, "use_local_exchange", False):
            return

        user_id, account_id = self._get_current_user_and_account_id()
        if user_id is None or account_id is None:
            return

        symbol = self.md.current_symbol() if hasattr(self.md, "current_symbol") else ""
        if not symbol:
            return

        # 1) DB에서 시장가 매수 실행 (IOC)
        res = self.db.place_market_buy(user_id, account_id, symbol, qty, ioc=True)

        # 2) 체결 리스트 (키 이름이 trades 또는 fills일 수 있음)
        fills = res.get("fills") or res.get("trades") or []

        # 3) 체결/잔고테이블 갱신
        self._append_fills_and_update_balance(account_id, fills)

        # 4) 호가/오더북 갱신
        try:
            snap = self.md.fetch_depth()
            if snap:
                self._apply_depth(snap)
        except Exception:
            pass

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
    def _apply_depth(self, snap: "DepthSnapshot"):
        """
        DepthSnapshot:
            snap.bids, snap.asks, snap.mid
        """
        self.last_depth = snap

        mid = snap.mid or 0.0

        # 1) 오더북 UI 갱신
        self.ob_table.set_orderbook(snap.bids, snap.asks, mid)

        # 2) 현재 심볼에 대해서만 마크투마켓
        symbol = self.md.current_symbol() if hasattr(self.md, "current_symbol") else ""

        prices_for_mtm: dict[str, float] = {}
        if symbol:
            prices_for_mtm[symbol] = mid

        if prices_for_mtm and hasattr(self.account, "mark_to_market"):
            self.account.mark_to_market(prices_for_mtm)

        # 3) 테이블 갱신용 가격 dict 전체 만들기
        state = self.account.state
        positions = state.get("positions", [])

        prices_for_table: dict[str, float] = {}
        for p in positions:
            sym = p["symbol"]
            if sym == symbol:
                prices_for_table[sym] = mid or p.get("last_price", p.get("avg_price", 0.0))
            else:
                prices_for_table[sym] = p.get("last_price", p.get("avg_price", 0.0))

        # 4) 테이블 렌더
        self.balance_table.render_positions(positions, prices_for_table)

    def _load_account_from_summary(self, summary: dict):
        """
        DB의 get_account_summary(account_id) 결과를 SimAccount에 로드
        summary: {"balance": float, "positions": [DictRow, ...]}
        """
        # 현금
        self.account.cash = float(summary.get("balance", 0.0))

        # 포지션 초기화
        self.account.positions.clear()

        for row in summary.get("positions", []):
            symbol = row["symbol"]
            qty = float(row["qty"])
            avg_price = float(row["avg_price"])

            pos = self.account._get_or_create_position(symbol)
            pos.position = qty
            pos.avg_price = avg_price
            # last_price / pnl은 나중에 mark_to_market에서 계산

    def _refresh_balance_table_from_db(self, account_id: int):
        """
        DB에서 계좌 요약을 가져와서 SimAccount에 로드하고,
        마크투마켓 후 BalanceTable을 갱신한다.
        """
        # 1) DB에서 요약 읽기
        summary = self.db.get_account_summary(account_id)
        self._load_account_from_summary(summary)

        # 2) SimAccount.state 가져오기
        state = self.account.state
        positions = state.get("positions", [])

        # 3) 심볼별 현재가 dict 만들기
        prices: dict[str, float] = {}
        for p in positions:
            sym = p["symbol"]

            cur = None
            # md에 심볼별 현재가 함수가 있으면 사용
            if hasattr(self.md, "get_last_price"):
                try:
                    cur = self.md.get_last_price(sym)
                except Exception:
                    cur = None

            if cur is None:
                # 일단 last_price → 없으면 avg_price fallback
                cur = p.get("last_price", p.get("avg_price", 0.0))

            prices[sym] = float(cur)

        # 4) 계좌 마크투마켓
        if hasattr(self.account, "mark_to_market"):
            self.account.mark_to_market(prices)

        # 5) MTM 반영된 최신 state로 다시 positions 가져오기
        state = self.account.state
        positions = state.get("positions", [])

        # 6) 테이블 렌더
        self.balance_table.render_positions(positions, prices)

    # -------------------------------------------------
    # 체결 처리 + 잔고 업데이트 + DB 기록
    # -------------------------------------------------

    def _append_fills_and_update_balance(self, account_id: int, fills: List[Any]):
        """
        체결 리스트를 UI에 반영하고,
        SimAccount/DB 잔고/포지션을 갱신한 뒤,
        마지막에 DB 기준으로 다시 읽어서 테이블을 리프레시한다.
        """
        if not fills:
            return

        delta_cash = 0.0  # 이번 체결들로 인한 총 현금 변화량

        for f in fills:
            # ---- side, price, qty, symbol 안전하게 꺼내기 ----
            if isinstance(f, dict):
                side_raw = f.get("side")
                price = float(f.get("price", 0.0))
                qty = float(f.get("qty", 0.0))
                symbol = f.get("symbol") or (
                    self.md.current_symbol() if hasattr(self.md, "current_symbol") else ""
                )
            else:
                side_obj = getattr(f, "side", None)
                side_raw = getattr(side_obj, "side", side_obj)
                price = float(getattr(f, "price", 0.0))
                qty = float(getattr(f, "qty", 0.0))
                symbol = getattr(f, "symbol", None) or (
                    self.md.current_symbol() if hasattr(self.md, "current_symbol") else ""
                )

            if not symbol:
                continue

            side_str = str(side_raw).upper()
            notional = price * qty

            # ---- 1) 체결표 UI ----
            self.trades.add_fill(side_str, price, int(qty))

            # ---- 2) SimAccount 포지션 반영 ----
            self.account.apply_fill(symbol, side_str, price, qty)

            # ---- 3) 현금 변화량 계산 ----
            if side_str == "SELL":
                delta_cash += notional  # 매도 → 돈 들어옴
            else:  # BUY
                delta_cash -= notional  # 매수 → 돈 나감

        # ---- 4) SimAccount 현금 반영 ----
        if delta_cash != 0.0:
            self.account.apply_cash(delta_cash)

        # ---- 5) DB accounts.balance 반영 ----
        if hasattr(self.db, "update_balance"):
            # ❗ update_balance가 "절대값"을 받는 함수라면 이렇게:
            self.db.update_balance(account_id, self.account.cash)

            # 만약 네 DBService가 "delta"를 받는다면 위 한 줄 대신:
            # self.db.update_balance(account_id, delta_cash)

        # ---- 6) DB positions 테이블 upsert ----
        if hasattr(self.db, "upsert_position"):
            for sym, pos in self.account.positions.items():
                self.db.upsert_position(
                    account_id=account_id,
                    symbol=sym,
                    qty=pos.position,
                    avg_price=pos.avg_price,
                )

        # ---- 7) 마지막으로, DB 기준으로 다시 읽어서 테이블 리프레시 ----
        self._refresh_balance_table_from_db(account_id)

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


    def _get_current_user_and_account_id(self):
        """
        편의용: 현재 로그인 유저/계좌 id 반환
        """
        user_email = getattr(self.auth, "current_user", None)
        if not user_email:
            return None, None

        user_id = self.db.get_user_id_by_email(user_email)
        if user_id is None:
            return None, None

        account_id = self.db.get_primary_account_id(user_id)
        if account_id is None:
            return None, None

        return user_id, account_id

