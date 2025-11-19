# controllers/orderbook_controller.py

class OrderBookController:
    """
    MatchingEngine 기반 UI 컨트롤러 (V2)
    - SimAccount 제거
    - OrderSimulator 제거
    - 모든 주문은 MatchingEngine API 호출
    """

    def __init__(
        self,
        md_service,
        orderbook_widget,
        trades_widget,
        balance_table,
        api_order,
        api_account,
        api_trade,
        auth,
    ):
        self.md = md_service
        self.ob_table = orderbook_widget
        self.trades_widget = trades_widget
        self.balance_table = balance_table
        self.api_order = api_order
        self.api_account = api_account
        self.api_trade = api_trade
        self.api_auth = auth
        self.last_depth = None

    # -----------------------------
    # 초기 UI 업데이트
    # -----------------------------
    def init_account_ui(self):
        user_id, account_id = self._get_user_and_account()
        if not user_id:
            return

        self.refresh_balance_table()
        self.refresh_trades()

        depth = self.md.fetch_depth()
        if depth:
            self._apply_depth(depth)

    # -----------------------------
    # 가격 폴링
    # -----------------------------
    def poll_and_render(self):
        depth = self.md.fetch_depth()
        if depth:
            self._apply_depth(depth)

    # -----------------------------
    # 주문 실행
    # -----------------------------
    def buy_market(self, qty):
        user_id, account_id = self._get_user_and_account()
        symbol = self.md.current_symbol()
        token = self.api_auth.access_token

        result = self.api_order.place_market(user_id, account_id, symbol, "BUY", qty)
        self.refresh_after_order(account_id)
        return result

    def sell_market(self, qty):
        user_id, account_id = self._get_user_and_account()
        symbol = self.md.current_symbol()
        token = self.api_auth.access_token

        result = self.api_order.place_market(user_id, account_id, symbol, "SELL", qty)
        self.refresh_after_order(account_id)
        return result

    def buy_limit(self, price, qty):
        user_id, account_id = self._get_user_and_account()
        symbol = self.md.current_symbol()
        token = self.api_auth.access_token

        result = self.api_order.place_limit(user_id, account_id, symbol, "BUY", price, qty)
        self.refresh_after_order(account_id)
        return result

    def sell_limit(self, price, qty):
        user_id, account_id = self._get_user_and_account()
        symbol = self.md.current_symbol()
        token = self.api_auth.access_token

        result = self.api_order.place_limit(user_id, account_id, symbol, "SELL", price, qty)
        self.refresh_after_order(account_id)
        return result

    # -----------------------------
    # 갱신
    # -----------------------------
    def refresh_balance_table(self):
        user_id, account_id = self._get_user_and_account()
        summary = self.api_account.get_account_summary(account_id)
        self.balance_table.render_from_summary(summary, self.md)

    def refresh_trades(self):
        user_id, _ = self._get_user_and_account()
        rows = self.api_trade.get_trades(user_id)
        self.trades_widget.render_from_api(rows)

    def refresh_after_order(self, account_id):
        self.refresh_balance_table()
        self.refresh_trades()

        depth = self.md.fetch_depth()
        if depth:
            self._apply_depth(depth)

    # -----------------------------
    # 시세 반영
    # -----------------------------
    def _apply_depth(self, snap):
        self.last_depth = snap
        self.ob_table.set_orderbook(snap.bids, snap.asks, snap.mid)

    # -----------------------------
    # 사용자/계좌 식별
    # -----------------------------
    def _get_user_and_account(self):
        user = self.api_auth.current_user
        if not user:
            return None, None

        user_id = user.get("user_id")
        account_id = self.api_account.get_primary_account_id(user_id)
        return user_id, account_id
