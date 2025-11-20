# controllers/orderbook_controller.py

class OrderBookController:
    """
    MatchingEngine 기반 UI 컨트롤러 (V2)
    - 오더북은 FastAPI /orderbook API로만 갱신
    - MarketDataService.fetch_depth()는 오더북에 사용하지 않음
    """

    def __init__(self, md_service, orderbook_widget, trades_widget,
                 balance_table, api_order, api_account, api_trade, orderbook_api, api_auth):

        self.md = md_service                      # 단순 symbol 관리용
        self.ob_table = orderbook_widget
        self.trades_widget = trades_widget
        self.balance_table = balance_table
        self.api_order = api_order
        self.api_account = api_account
        self.api_trade = api_trade
        self.api_orderbook = orderbook_api
        self.api_auth = api_auth
        self.cached_symbol = None

    # ============================================================
    # 초기 구성
    # ============================================================
    def init_account_ui(self):
        user_id, account_id = self._get_user_and_account()
        if not user_id:
            return

        self.refresh_balance_table()
        self.refresh_trades()
        self.refresh_orderbook()

    # ============================================================
    # 타이머에서 주기적으로 호출됨
    # ============================================================
    def poll_and_render(self):
        """오더북만 주기적으로 갱신"""
        self.refresh_orderbook()

    # ============================================================
    # 주문 실행
    # ============================================================
    def buy_market(self, qty):
        user_id, account_id = self._get_user_and_account()
        result = self.api_order.place_market(
            user_id, account_id, self.md.current_symbol(), "BUY", qty
        )
        self.refresh_after_order(account_id)
        return result

    def sell_market(self, qty):
        user_id, account_id = self._get_user_and_account()
        result = self.api_order.place_market(
            user_id, account_id, self.md.current_symbol(), "SELL", qty
        )
        self.refresh_after_order(account_id)
        return result

    def buy_limit(self, price, qty):
        user_id, account_id = self._get_user_and_account()
        result = self.api_order.place_limit(
            user_id, account_id, self.md.current_symbol(), "BUY", price, qty
        )
        self.refresh_after_order(account_id)
        return result

    def sell_limit(self, price, qty):
        user_id, account_id = self._get_user_and_account()
        result = self.api_order.place_limit(
            user_id, account_id, self.md.current_symbol(), "SELL", price, qty
        )
        self.refresh_after_order(account_id)
        return result

    # ============================================================
    # 주문 후 UI 갱신
    # ============================================================
    def refresh_after_order(self, account_id):
        self.refresh_balance_table()
        self.refresh_trades()
        self.refresh_orderbook()

    # ============================================================
    # 잔고 테이블
    # ============================================================
    def refresh_balance_table(self):
        user_id, account_id = self._get_user_and_account()
        summary = self.api_account.get_account_summary(account_id)
        self.balance_table.render_from_summary(summary, self.md)

    # ============================================================
    # 체결창 테이블
    # ============================================================
    def refresh_trades(self):
        user_id, _ = self._get_user_and_account()
        rows = self.api_trade.get_trades(user_id)
        self.trades_widget.render_from_api(rows)

    # ============================================================
    # ★ 오더북 갱신 (핵심)
    # ============================================================
    def refresh_orderbook(self):
        symbol = self.md.current_symbol().upper()

        # 1) Binance 실시간 호가
        snap = self.md.fetch_depth()
        if not snap:
            self.ob_table.render_from_api({"bids": [], "asks": []})
            return

        # 2) Local order DB qty/cnt
        local = self.api_orderbook.get_local_depth(symbol)

        # 딕셔너리로 변환 (빠른 lookup)
        local_bids = {float(x["price"]): x for x in local["bids"]}
        local_asks = {float(x["price"]): x for x in local["asks"]}

        # 3) merge
        bids = []
        for price, qty, _ in snap.bids:
            entry = local_bids.get(price, {"qty": 0, "cnt": 0})
            bids.append({
                "price": price,
                "binance_qty": qty,
                "qty": entry["qty"],
                "cnt": entry["cnt"]
            })

        asks = []
        for price, qty, _ in snap.asks:
            entry = local_asks.get(price, {"qty": 0, "cnt": 0})
            asks.append({
                "price": price,
                "binance_qty": qty,
                "qty": entry["qty"],
                "cnt": entry["cnt"]
            })

        # UI 렌더
        self.ob_table.render_from_api({
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "mid": snap.mid
        })

    # ============================================================
    # 공용
    # ============================================================
    def _get_user_and_account(self):
        user = self.api_auth.current_user
        if not user:
            return None, None
        user_id = user.get("user_id")
        account_id = self.api_account.get_primary_account_id(user_id)
        return user_id, account_id
