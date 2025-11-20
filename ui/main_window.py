# MainWindow.py (V2 API 기반 완전 리팩토링 버전)
import os
from pathlib import Path
from PyQt6 import QtWidgets, uic
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox
from widgets.TradePanel import TradePanel
# ---- Controllers / Services ----
from controllers.auth_controller_api import AuthControllerAPI
from controllers.orderbook_controller import OrderBookController
from controllers.orderbook_controller_api import OrderBookControllerAPI
from controllers.order_controller_api import OrdersControllerAPI
from controllers.account_controller_api import AccountControllerAPI
from controllers.trade_controller_api import TradeControllerAPI
from controllers.orderbook_api import OrderBookAPI
from controllers.orderbook_api_client import OrderBookAPIClient

from services.marketdata_service import MarketDataService

# ---- Widgets ----
from widgets.orderbook_table import OrderBookTable
from widgets.stocklist_table import StockListTable
from widgets.trades_table import TradesTable
from widgets.balance_table import BalanceTable
from widgets.ready_order_table import ReadyOrdersTable

from ui.login_dialog import LoginDialog
from widgets.open_account_dialog import OpenAccountDialog


class MainWindow(QtWidgets.QMainWindow):
    """
    MainWindow V2:
    - 모든 주문/체결/계좌/미체결은 API 기반
    - OrderBookController v2 와 동작
    - 로컬 시뮬레이터 제거
    """

    def __init__(self, use_mock=False, base_price=20000.0):
        super().__init__()

        # --- UI 파일 로드 ---
        RES_DIR = Path(__file__).resolve().parents[1] / "resources"
        ui_file = RES_DIR / "nasdaq_extended.ui"
        # ui_file = RES_DIR / "nasdaq_extended_with_trade_layout.ui"
        if not ui_file.exists():
            raise FileNotFoundError(f"UI file not found: {ui_file}")

        uic.loadUi(str(ui_file), self)
        self.setWindowTitle("EXTENDED")

        depth_levels = 10

        # --- 서비스/API 객체 생성 ---
        self.authApi = AuthControllerAPI()
        self.orderApi = OrdersControllerAPI()
        self.accountApi = AccountControllerAPI()
        self.tradeApi = TradeControllerAPI()
        self.orderBookApi = OrderBookAPIClient()

        # Market Data
        self.md = MarketDataService(
            use_mock=use_mock,
            provider="BINANCE",
            symbol="solusdt",
            rows=depth_levels
        )
        # if not use_mock:
        #     self.md.start_oracle()

        # --- 심볼 셀렉터 ---
        self._bind_symbol_selector()

        # --- 테이블 래핑 ---
        self.orderbook = OrderBookTable(self.table_hoga)
        self.stocklist = StockListTable(self.table_stocklist)
        self.trades = TradesTable(self.table_trades)
        self._ensure_ready_orders_widget()
        self._ensure_balance_widget()

        # tradePanel = TradePanel(self.trades.table)
        # self.trade_layout.addWidget(tradePanel)

        # --- 컨트롤러 연결 ---
        self.ctrl = OrderBookController(
            self.md,
            self.orderbook,
            self.trades,
            self.balance_table,
            self.orderApi,
            self.accountApi,
            self.tradeApi,
            self.orderBookApi,
            self.authApi
        )

        # --- 버튼 핸들러 연결 ---
        self.button_sell_market_price.clicked.connect(self._on_sell_mkt)
        self.button_buy_market_price.clicked.connect(self._on_buy_mkt)
        self.button_sell_fix_price.clicked.connect(self._on_sell_lmt)
        self.button_buy_fix_price.clicked.connect(self._on_buy_lmt)

        if hasattr(self, "btn_cancel_orders"):
            self.btn_cancel_orders.clicked.connect(self._on_cancel_selected_orders)

        # --- 메뉴 ---
        self._build_menu()

        # --- 타이머 (시세/잔고/미체결 리프레시) ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(200)

    def _update_orderbook(self):
        symbol = self.md.current_symbol().upper()
        data = self.orderBookApi.get_depth(symbol)
        self.orderbook.render_from_api(data)

    # --------------------------------------------------------
    # 심볼 선택기
    # --------------------------------------------------------
    def _bind_symbol_selector(self):
        combo = getattr(self, "drpbox_symbols", None)
        if not isinstance(combo, QtWidgets.QComboBox):
            QtWidgets.QMessageBox.warning(self, "ui", "drpbox_symbols 콤보박스를 찾을 수 없습니다.")
            return

        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
        combo.clear()
        combo.addItems(symbols)

        cur = self.md.current_symbol().upper()
        if cur not in symbols:
            combo.insertItem(0, cur)

        combo.setCurrentText(cur)
        combo.currentTextChanged.connect(self._on_symbol_changed)

    def _on_symbol_changed(self, sym: str):
        sym = (sym or "").strip().upper()
        if not sym:
            return

        # MarketDataService에도 반드시 대문자로 전달!
        self.md.set_symbol(sym)

        # UI 초기화
        try:
            self.orderbook.render_from_api([], [])
        except Exception:
            pass

        self.trades.trades.clear()

        # Trade 로드
        self._load_trades_from_api()

        # 강제 depth 갱신
        self.ctrl.poll_and_render()

        email = (self.authApi.current_user.get("email")
                 if self.authApi.current_user else "Logged out")
        self.setWindowTitle(f"NASDAQ EXTENDED — {email} — {sym}")

    # --------------------------------------------------------
    # 미체결 테이블 바인드
    # --------------------------------------------------------
    def _ensure_ready_orders_widget(self):
        tabw = getattr(self, "table_ready_trades", None)
        if not isinstance(tabw, QtWidgets.QTabWidget):
            raise RuntimeError("table_ready_trades(QTabWidget)을 찾을 수 없음")

        ready_trades_page = tabw.findChild(QtWidgets.QWidget, "tab_ready_trades")

        if ready_trades_page is None:
            for i in range(tabw.count()):
                if tabw.tabText(i) == "미체결":
                    ready_trades_page = tabw.widget(i)
                    ready_trades_page.setObjectName("tab_ready_trades")
                    break

        if ready_trades_page is None:
            ready_trades_page = QtWidgets.QWidget()
            ready_trades_page.setObjectName("tab_ready_trades")
            ready_trades_page.setLayout(QtWidgets.QVBoxLayout())
            tabw.addTab(ready_trades_page, "미체결")

        table = ready_trades_page.findChild(QtWidgets.QTableWidget, "tab_ready_trades")
        if table is None:
            table = QtWidgets.QTableWidget(ready_trades_page)
            table.setObjectName("tab_ready_trades")
            ready_trades_page.layout().addWidget(table)

        self.ready_orders = ReadyOrdersTable(table)

    # --------------------------------------------------------
    # 잔고 테이블 바인드
    # --------------------------------------------------------
    def _ensure_balance_widget(self):
        tabw = getattr(self, "table_ready_trades", None)
        if not isinstance(tabw, QtWidgets.QTabWidget):
            raise RuntimeError("table_ready_trades(QTabWidget)을 찾을 수 없음")

        # 잔고 탭 찾기
        balance_page = tabw.findChild(QtWidgets.QWidget, "tab_balance_table")
        if balance_page is None:
            for i in range(tabw.count()):
                if tabw.tabText(i) == "잔고":
                    balance_page = tabw.widget(i)
                    balance_page.setObjectName("tab_balance_table")
                    break

        if balance_page is None:
            balance_page = QtWidgets.QWidget()
            balance_page.setObjectName("tab_balance_table")
            balance_page.setLayout(QtWidgets.QVBoxLayout())
            tabw.addTab(balance_page, "잔고")

        table = balance_page.findChild(QtWidgets.QTableWidget, "tab_balance_table")
        if table is None:
            table = QtWidgets.QTableWidget(balance_page)
            table.setObjectName("tab_balance_table")
            balance_page.layout().addWidget(table)

        self.balance_table = BalanceTable(table)

    # --------------------------------------------------------
    # 타이머
    # --------------------------------------------------------
    def _on_timer(self):
        self.ctrl.poll_and_render()
        self._refresh_balance()
        # self._update_orderbook()
        self._reload_working_orders()
        # self._refresh_orders_and_trades()

    # --------------------------------------------------------
    # 로그인
    # --------------------------------------------------------
    def _require_login(self):
        if self.authApi.current_user:
            return True
        QtWidgets.QMessageBox.warning(self, "Login", "먼저 로그인하세요.")
        self._do_login()
        return bool(self.authApi.current_user)

    def _do_login(self):
        dlg = LoginDialog(self)
        if dlg.exec():
            user, pw = dlg.credentials()
            if self.authApi.login(user, pw):
                # ★★ 여기에서 토큰 전달 ★★
                token = self.authApi.access_token
                self.accountApi.access_token = token
                self.orderApi.access_token = token
                self.tradeApi.access_token = token

                self._apply_login_ui()
                QtWidgets.QMessageBox.information(self, "Login", f"Welcome, {user}!")
                self._load_trades_from_api()
                self._reload_working_orders()

            else:
                QtWidgets.QMessageBox.warning(self, "Login", "계정 정보가 올바르지 않습니다.")

    # 로그인 UI 반영
    def _apply_login_ui(self):
        user = self.authApi.current_user
        email = user.get("email") if user else "Logged out"
        self.setWindowTitle(f"NASDAQ EXTENDED — {email}")

    # --------------------------------------------------------
    # 주문 버튼
    # --------------------------------------------------------
    def _on_sell_mkt(self):
        if not self._require_login():
            return
        qty, ok = QtWidgets.QInputDialog.getInt(self, "시장가 매도", "수량:", 1, 1)
        if ok:
            self.ctrl.sell_market(qty)
            self._refresh_orders_and_trades()

    def _on_buy_mkt(self):
        if not self._require_login():
            return
        qty, ok = QtWidgets.QInputDialog.getInt(self, "시장가 매수", "수량:", 1, 1)
        if ok:
            self.ctrl.buy_market(qty)
            self._refresh_orders_and_trades()

    def _on_sell_lmt(self):
        if not self._require_login():
            return

        qty, ok1 = QtWidgets.QInputDialog.getInt(self, "지정가 매도", "수량:", 1, 1)
        if not ok1:
            return

        px, ok2 = QtWidgets.QInputDialog.getDouble(self, "지정가 매도", "가격:", 0.0, 0, 1e12, 2)
        if not ok2 or px <= 0:
            return

        user = self.authApi.current_user
        user_id = user.get("user_id")
        account_id = self.accountApi.get_primary_account_id(user_id)
        symbol = self.md.current_symbol()

        res = self.orderApi.place_limit(
            user_id=user_id,
            account_id=account_id,
            symbol=symbol,
            side="SELL",
            price=px,
            qty=qty,
        )

        if not res:
            QtWidgets.QMessageBox.warning(self, "Order", "주문 저장 실패")
            return

        self._refresh_orders_and_trades()
        QtWidgets.QMessageBox.information(self, "Order", "지정가 매도 주문이 접수되었습니다.")

    def _on_buy_lmt(self):
        if not self._require_login():
            return

        qty, ok1 = QtWidgets.QInputDialog.getInt(self, "지정가 매수", "수량:", 1, 1)
        if not ok1:
            return

        px, ok2 = QtWidgets.QInputDialog.getDouble(self, "지정가 매수", "가격:", 0.0, 0, 1e12, 2)
        if not ok2 or px <= 0:
            return

        user = self.authApi.current_user
        user_id = user.get("user_id")
        account_id = self.accountApi.get_primary_account_id(user_id)
        symbol = self.md.current_symbol()

        res = self.orderApi.place_limit(
            user_id=user_id,
            account_id=account_id,
            symbol=symbol,
            side="BUY",
            price=px,
            qty=qty,
        )

        if not res:
            QtWidgets.QMessageBox.warning(self, "Order", "주문 저장 실패")
            return

        self._refresh_orders_and_trades()
        QtWidgets.QMessageBox.information(self, "Order", "지정가 매수 주문이 접수되었습니다.")

    # --------------------------------------------------------
    # 취소
    # --------------------------------------------------------
    def _on_cancel_selected_orders(self):
        order_ids = self.ready_orders.get_checked_order_ids()
        if not order_ids:
            QMessageBox.information(self, "안내", "취소할 주문을 선택하세요.")
            return

        reply = QtWidgets.QMessageBox.question(
            self, "일괄 취소", f"{len(order_ids)}건의 주문을 취소하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.orderApi.cancel_orders(order_ids)
        self._refresh_orders_and_trades()

        QtWidgets.QMessageBox.information(self, "취소", f"{len(order_ids)}건의 주문이 취소되었습니다.")

    # --------------------------------------------------------
    # 조회 & UI 갱신
    # --------------------------------------------------------
    def _reload_working_orders(self):
        user = self.authApi.current_user
        if not user:
            self.ready_orders.render_from_api([])
            return

        user_id = user.get("user_id")
        rows = self.orderApi.get_user_working_orders(user_id)
        self.ready_orders.render_from_api(rows)

    def _refresh_orders_and_trades(self):
        user = self.authApi.current_user
        if not user:
            return

        user_id = user.get("user_id")

        working = self.orderApi.get_user_working_orders(user_id)
        trades = self.tradeApi.get_trades()

        self.ready_orders.render_from_api(working)
        self.trades.render_from_api(trades)

    def _load_trades_from_api(self):
        token = self.authApi.access_token
        if not token:
            QtWidgets.QMessageBox.warning(self, "Login", "먼저 로그인하세요.")
            return

        try:
            rows = self.tradeApi.get_trades()
            self.trades.render_from_api(rows)

        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))

    def _refresh_balance(self):
        user = self.authApi.current_user
        if not user:
            return

        user_id = user.get("user_id")
        account_id = self.accountApi.get_primary_account_id(user_id)
        if not account_id:
            return

        summary = self.accountApi.get_account_summary(account_id)
        self.balance_table.render_from_summary(summary, self.md)

    # --------------------------------------------------------
    # 메뉴
    # --------------------------------------------------------
    def _build_menu(self):
        mb = self.menuBar()
        try:
            mb.setNativeMenuBar(False)
        except:
            pass

        menu = mb.addMenu("File")

        act_login = menu.addAction("Login…")
        act_login.triggered.connect(self._toggle_login)

        act_signup = menu.addAction("Sign Up…")
        act_signup.triggered.connect(self._open_signup_dialog)

        act_open_account = menu.addAction("Open Account")
        act_open_account.triggered.connect(self._open_account_dialog)

        menu.addSeparator()
        act_quit = menu.addAction("Quit")
        act_quit.triggered.connect(self.close)

    def _toggle_login(self):
        if self.authApi.current_user:
            email = self.authApi.logout()
            self._apply_login_ui()
            QtWidgets.QMessageBox.information(self, "Logout", f"{email} 로그아웃")
        else:
            self._do_login()

    def _open_account_dialog(self):
        token = self.authApi.access_token
        if not token:
            QtWidgets.QMessageBox.warning(self, "Login", "먼저 로그인하세요.")
            return
        user = self.authApi.current_user
        dlg = OpenAccountDialog(user.get("user_id"),
                                accountApi=self.accountApi,
                                parent=self,
                                )
        dlg.exec()

    def _open_signup_dialog(self):
        from widgets.signup_dialog import SignupDialog
        dlg = SignupDialog(None, self)
        dlg.exec()

    # --------------------------------------------------------
    # 종료 처리
    # --------------------------------------------------------
    def closeEvent(self, e):
        self.timer.stop()
        # self.md.close()
        super().closeEvent(e)



# 단독 실행용 (프로젝트에서 main.py가 따로 있으면 생략 가능)
if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(use_mock = False, base_price=20000.0)
    win.show()
    sys.exit(app.exec())
