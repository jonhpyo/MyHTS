# MainWindows.py
import os
from services.db_service import DBService
from pathlib import Path
import psycopg2
from ib_insync import util

from services.matching_engine import MatchingEngine
from widgets.open_account_dialog import OpenAccountDialog

util.useQt()

# PyQt6 우선, 실패 시 PyQt5 폴백
try:
    from PyQt6 import QtWidgets, uic
    from PyQt6.QtCore import QTimer
    _QT6 = True
except Exception:
    from PyQt5 import QtWidgets, uic
    from PyQt5.QtCore import QTimer
    _QT6 = False

# --- 프로젝트 모듈 ---
from controllers.auth_controller import AuthController
from controllers.auth_controller_api import AuthControllerAPI
from controllers.orderbook_controller import OrderBookController
from services.marketdata_service import MarketDataService
from services.order_simulator import OrderSimulator
from services.simaccount import SimAccount

from widgets.orderbook_table import OrderBookTable
from widgets.stocklist_table import StockListTable
from widgets.trades_table import TradesTable
from widgets.balance_table import BalanceTable
from widgets.ready_order_table import ReadyOrdersTable

from ui.login_dialog import LoginDialog


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, use_mock: bool = False, base_price: float = 20000.0):
        super().__init__()

        # --- UI 파일 로드 ---
        RES_DIR = Path(__file__).resolve().parents[1] / "resources"
        ui_file = RES_DIR / "nasdaq_extended.ui"
        if not ui_file.exists():
            raise FileNotFoundError(f"UI file not found: {ui_file}")
        uic.loadUi(str(ui_file), self)

        self.setWindowTitle("NASDAQ EXTENDED")

        depth_levels = 10
        # --- 상태/서비스 초기화 ---
        self.auth = AuthController()
        self.authApi = AuthControllerAPI()

        initial_cash = float(os.getenv("INITIAL_CASH", "0"))
        # self.use_local_exchange = "True" os.getenv("USE_LOCAL_EXCHANGE", "False")
        self.use_local_exchange = "True"
        self.account = SimAccount()

        self.md = MarketDataService(use_mock=use_mock, provider="BINANCE", symbol="solusdt", rows=depth_levels,)
        # if not use_mock:
        #     self.md.start_ib()
        # self.md.start_binance()
        if not use_mock:
            self.md.start_oracle()

        self.db = DBService()
        self.matching = MatchingEngine(self.db)
        self.sim = OrderSimulator()

        self._bind_symbol_selector()


        # --- 위젯 래퍼 바인딩 ---
        self.orderbook = OrderBookTable(self.table_hoga, row_count=depth_levels*2+1, base_index=depth_levels)
        self.stocklist = StockListTable(self.table_stocklist, rows=10)
        self.trades = TradesTable(self.table_trades, max_rows=30)

        # 미체결/잔고 탭 연결
        self._ensure_ready_orders_widget()
        self._ensure_balance_widget()

        # --- 컨트롤러 ---
        self.ctrl = OrderBookController(
            md_service=self.md,
            orderbook_widget=self.orderbook,
            trades_widget=self.trades,
            sim=self.sim,
            account=self.account,
            balance_table=self.balance_table,
            db = self.db,
            auth = self.auth,
            use_local_exchange=bool(self.use_local_exchange),
        )

        # --- 버튼 핸들러 연결 ---
        # 주의: UI의 오브젝트명이 정확히 아래와 같아야 합니다.
        # button_sell_market_price (시장가 매도), button_buy_market_price (시장가 매수), button_sell_fix_price (지정가 매도)
        self.button_sell_market_price.clicked.connect(self._on_sell_mkt)
        self.button_buy_market_price.clicked.connect(self._on_buy_mkt)
        self.button_sell_fix_price.clicked.connect(self._on_sell_lmt)
        self.button_buy_fix_price.clicked.connect(self._on_buy_lmt)

        # ✅ 미체결 일괄취소 버튼
        if hasattr(self, "btn_cancel_orders"):
            self.btn_cancel_orders.clicked.connect(self._on_cancel_selected_orders)

        # --- 메뉴/로그인 ---
        self._build_menu()

        # --- 타이머: 시세 폴링 및 UI 반영 ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(150)

        # 초기 렌더
        # self.ready_orders.render(self.sim.working)
        # self.balance_table.render(self.account.state)

    # 클래스 메서드 추가
    def _bind_symbol_selector(self):
        """
        .ui에 있는 QComboBox 'drpbox_symbols'를 사용해 심볼 선택/변경 기능 연결
        """
        combo = getattr(self, "drpbox_symbols", None)
        if not isinstance(combo, QtWidgets.QComboBox):
            QtWidgets.QMessageBox.warning(self, "UI", "drpbox_symbols 콤보를 찾을 수 없습니다.")
            return

        # 원하는 심볼 목록 (바이낸스 현물 예시)
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
        combo.clear()
        combo.addItems(symbols)

        # MarketDataService 와 현재 심볼 동기화
        cur = (self.md.current_symbol() if hasattr(self.md, "current_symbol") else "BTCUSDT")
        cur = (cur or "BTCUSDT").upper()

        if cur not in symbols:
            combo.insertItem(0, cur)
        combo.setCurrentText(cur)

        # 변경 이벤트 연결
        combo.currentTextChanged.connect(self._on_symbol_changed)

    # MainWindows.py
    def _on_symbol_changed(self, sym: str):
        sym = (sym or "").strip().upper()
        if not sym:
            return

        # md에 반영
        if hasattr(self.md, "set_symbol"):
            self.md.set_symbol(sym.lower())  # BINANCE 는 소문자

        # 화면 초기화
        self.ctrl.last_depth = None
        try:
            self.orderbook.set_orderbook([], [], 0.0)
        except Exception:
            pass
        if hasattr(self.trades, "trades"):
            self.trades.trades.clear()
            self._load_trades_from_api()

        # 바로 한 번 폴링해서 새 심볼 호가를 강제 갱신
        try:
            self.ctrl.poll_and_render()
        except Exception as e:
            print("[MainWindow] poll_and_render on symbol change error:", e)

        self.setWindowTitle(
            f"NASDAQ EXTENDED — {self.authApi.current_user or 'Logged out'} — {sym}"
        )

    # --------------------------
    # 탭/테이블 바인딩 헬퍼
    # --------------------------
    def _ensure_ready_orders_widget(self):
        """
        QTabWidget(table_ready_trades) 내부의 QTableWidget(tap_ready_trades)을 찾아
        ReadyOrdersTable로 래핑. 없으면 생성해서 1번 탭에 추가.
        """
        tabw = getattr(self, "table_ready_trades", None)  # QTabWidget
        table = None


        if isinstance(tabw, QtWidgets.QTabWidget):
            tabw.tabBar().setStyleSheet("""
                    QTabBar::tab {
                        width: 120px;       /* 각 탭의 고정 너비 */
                        height: 30px;       /* 탭 높이 */
                        font-size: 13px;    /* 폰트 크기 */
                    }
                """
            )

            table = tabw.findChild(QtWidgets.QTableWidget, "tap_ready_trades")

            if table is None:
                # 첫 탭 컨테이너 확보
                if tabw.count() == 0:
                    container = QtWidgets.QWidget()
                    container.setObjectName("tab_ready_trades_container")
                    container.setLayout(QtWidgets.QVBoxLayout(container))
                    tabw.addTab(container, "미체결")
                else:
                    container = tabw.widget(0)
                    if container.layout() is None:
                        container.setLayout(QtWidgets.QVBoxLayout(container))

                table = QtWidgets.QTableWidget(container)
                table.setObjectName("tap_ready_trades")
                container.layout().addWidget(table)
        else:
            # 탭 위젯이 없을 때의 안전장치 (필요 시 원하는 위치에 table 배치)
            table = getattr(self, "tap_ready_trades", None)
            if table is None:
                table = QtWidgets.QTableWidget(self)
                table.setObjectName("tap_ready_trades")

        self.ready_orders = ReadyOrdersTable(table)

    # MainWindows.py 안의 _ensure_balance_widget 교체본
    def _ensure_balance_widget(self):
        """
        table_ready_trades(QTabWidget) 안에 있는 '잔고' 탭(page: objectName='tab_balance_table')을 찾아
        그 안의 QTableWidget을 BalanceTable로 래핑. 없으면 최소한으로 보완.
        """
        tabw = getattr(self, "table_ready_trades", None)
        if not isinstance(tabw, QtWidgets.QTabWidget):
            raise RuntimeError("QTabWidget 'table_ready_trades' 를 찾지 못했습니다.")

        # 1) 잔고 탭 페이지 찾기 (objectName 우선, 없으면 탭 텍스트)
        balance_page = tabw.findChild(QtWidgets.QWidget, "tab_balance_table")
        if balance_page is None:
            for i in range(tabw.count()):
                if tabw.tabText(i) == "잔고":
                    balance_page = tabw.widget(i)
                    # 앞으로 쉽게 찾도록 objectName 부여
                    balance_page.setObjectName("tab_balance_table")
                    break

        # 2) 없으면 생성 (백업)
        if balance_page is None:
            balance_page = QtWidgets.QWidget()
            balance_page.setObjectName("tab_balance_table")
            balance_page.setLayout(QtWidgets.QVBoxLayout(balance_page))
            tabw.addTab(balance_page, "잔고")
        if balance_page.layout() is None:
            balance_page.setLayout(QtWidgets.QVBoxLayout(balance_page))

        # 3) 잔고 테이블 찾기: 우선 objectName='tab_balance_table' 인 QTableWidget,
        #    없으면 잔고 탭 안의 첫 번째 QTableWidget, 그래도 없으면 생성
        table = balance_page.findChild(QtWidgets.QTableWidget, "tab_balance_table")
        if table is None:
            table = balance_page.findChild(QtWidgets.QTableWidget)
        if table is None:
            table = QtWidgets.QTableWidget(balance_page)
            table.setObjectName("tab_balance_table")
            balance_page.layout().addWidget(table)

        # 4) 래핑
        self.balance_table = BalanceTable(table)

    def _refresh_balance(self):
        user_email = self.auth.current_user
        if not user_email:
            return
        user_id = self.db.get_user_id_by_email(user_email)
        if not user_id:
            return
        account_id = self.db.get_primary_account_id(user_id)
        if not account_id:
            return

        summary = self.db.get_account_summary(account_id)
        positions = summary["positions"]
        balance = summary["balance"]

        # 시세는 MarketDataService에서 현재가 dict로 받음
        prices = self.md.get_latest_prices_dict() if hasattr(self.md, "get_latest_prices_dict") else {}

        self.balance_table.render_positions(positions, prices)

    # --------------------------
    # 타이머/버튼/로그인
    # --------------------------
    def _on_timer(self):
        self.ctrl.poll_and_render()  # 시세/호가
        self._refresh_balance()
        # if self.auth.current_user:
        #     user_id = self.db.get_user_id_by_email(self.auth.current_user)
        #     if user_id:
        #         rows = self.db.get_working_orders_by_user(user_id, limit=100)
        #         self.ready_orders.render_from_db(rows)
        # else:
            # 로그인 안 되어 있으면 빈 화면
            # self.ready_orders.render([])

    def _require_login(self) -> bool:
        if self.authApi.current_user:
            return True
        QtWidgets.QMessageBox.warning(self, "Login", "먼저 로그인하세요.")
        self._do_login()
        return bool(self.authApi.current_user)

    def _on_sell_mkt(self):
        if not self._require_login():
            return
        qty, ok = QtWidgets.QInputDialog.getInt(self, "시장가 매도", "수량:", 1, 1)
        if ok:
            self.ctrl.sell_market(qty)
            # self.ready_orders.render(self.sim.working)
            self.ready_orders.render_from_db(self.sim.working)
            self._refresh_orders_and_trades()

    def _on_buy_mkt(self):
        if not self._require_login():
            return
        qty, ok = QtWidgets.QInputDialog.getInt(self, "시장가 매수", "수량:", 1, 1)
        if ok:
            self.ctrl.buy_market(qty)
            # 미체결 갱신 주기 호출 제거되어 있어야 체크박스 유지됨!
            if hasattr(self, "ready_orders"):
                self._refresh_orders_and_trades()
                pass

    def _on_sell_lmt(self):
        if not self._require_login():
            return

        qty, ok1 = QtWidgets.QInputDialog.getInt(self, "지정가 매도", "수량:", 1, 1)
        if not ok1:
            return
        px, ok2 = QtWidgets.QInputDialog.getDouble(self, "지정가 매도", "가격:", 0.0, 0, 1e12, 2)
        if not ok2 or px <= 0:
            return

        # 로그인 사용자/계좌 찾기
        user_email = self.authApi.current_user
        user_id = self.db.get_user_id_by_email(user_email)
        account_id = self.db.get_primary_account_id(user_id)  # 이미 만든 메서드라고 가정

        symbol = self.md.current_symbol()  # 예: 'SOLUSDT'

        # 1) 주문을 DB에 INSERT
        order_id = self.db.insert_order(
            user_id=user_id,
            account_id=account_id,
            symbol=symbol,
            side="SELL",
            price=px,
            qty=qty,
        )

        if not order_id:
            QtWidgets.QMessageBox.warning(self, "Order", "주문 저장 실패")
            return

        # 2) 매칭 엔진 호출 → 다른 사람 주문과 맞으면 체결 발생
        self.matching.match_symbol(symbol)

        # 3) UI 갱신 (미체결 / 체결)
        self._refresh_orders_and_trades()

        QtWidgets.QMessageBox.information(self, "Order", f"지정가 매도 주문이 접수되었습니다. (id={order_id})")

    def _on_buy_lmt(self):
        if not self._require_login():
            return

        # 1) 수량 입력
        qty, ok1 = QtWidgets.QInputDialog.getInt(
            self, "지정가 매수", "수량:", 1, 1
        )
        if not ok1:
            return

        # 2) 가격 입력
        px, ok2 = QtWidgets.QInputDialog.getDouble(
            self, "지정가 매수", "가격:", 0.0, 0, 1e12, 2
        )
        if not ok2 or px <= 0:
            return
        #
        # 로그인 사용자/계좌 찾기
        user_email = self.authApi.current_user
        user_id = self.db.get_user_id_by_email(user_email)
        account_id = self.db.get_primary_account_id(user_id)  # 이미 만든 메서드라고 가정

        symbol = self.md.current_symbol()  # 예: 'SOLUSDT'

        # 1) 주문을 DB에 INSERT
        order_id = self.db.insert_order(
            user_id=user_id,
            account_id=account_id,
            symbol=symbol,
            side="BUY",
            price=px,
            qty=qty,
        )

        if not order_id:
            QtWidgets.QMessageBox.warning(self, "Order", "주문 저장 실패")
            return

        # 2) 매칭 엔진 호출 → 다른 사람 주문과 맞으면 체결 발생
        self.matching.match_symbol(symbol)

        # 3) UI 갱신 (미체결 / 체결)
        self._refresh_orders_and_trades()

        QtWidgets.QMessageBox.information(self, "Order", f"지정가 매수 주문이 접수되었습니다. (id={order_id})")

        # # 3) 컨트롤러에 전달
        # remain = self.ctrl.buy_limit(px, qty)
        #
        # # 4) 미체결 테이블 갱신 (ReadyOrdersTable)
        # self.ready_orders.render(self.sim.working)
        #
        # # 5) 잔량 있으면 안내
        # if remain:
        #     QtWidgets.QMessageBox.information(
        #         self,
        #         "지정가",
        #         f"잔량 {remain} 대기 등록",
        #     )

    def _on_cancel_selected_orders(self):
        """미체결 테이블에서 선택된 주문들을 일괄 취소"""
        order_ids = self.ready_orders.get_checked_order_ids()
        if not order_ids:
            QtWidgets.QMessageBox.information(self, "취소", "선택된 주문이 없습니다.")
            return

        reply = QtWidgets.QMessageBox.question(self,"일괄 취소",f"{len(order_ids)}건의 주문을 취소하시겠습니까?", QtWidgets.QMessageBox.StandardButton.Yes| QtWidgets.QMessageBox.StandardButton.No,)
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        # DB에서 취소 처리
        self.db.cancel_orders(order_ids)

        # 화면 갱신 (미체결/호가/잔고 등)
        if hasattr(self, "_refresh_orders_and_trades"):
            self._refresh_orders_and_trades()
        else:
            # 최소한 미체결 테이블은 새로 불러오기
            self._reload_working_orders()

        QtWidgets.QMessageBox.information(
            self, "취소", f"{len(order_ids)}건의 주문이 취소되었습니다."
        )

    def _reload_working_orders(self):
        user_email = self.authApi.current_user
        if not user_email:
            return
        user_id = self.db.get_user_id_by_email(user_email)
        rows = self.db.get_working_orders_by_user(user_id)
        self.ready_orders.render_from_db(rows)


    def _build_menu(self):
        mb = self.menuBar()
        try:
            mb.setNativeMenuBar(False)
        except Exception:
            pass

        menu = mb.addMenu("File")

        # 로그인/로그아웃
        self.act_login_logout = menu.addAction("Login…")
        self.act_login_logout.setShortcut("Ctrl+L" if os.name != "posix" else "Cmd+L")
        self.act_login_logout.triggered.connect(self._toggle_login)

        # ✅ 회원가입 추가
        act_signup = menu.addAction("Sign Up…")
        act_signup.setShortcut("Ctrl+N" if os.name != "posix" else "Cmd+N")
        act_signup.triggered.connect(self._open_signup_dialog)

        act_open_account = menu.addAction("open Account")
        act_open_account.triggered.connect(self._open_account_dialog)

        # 🧪 더미 체결 추가 (테스트용)
        act_dummy_trade = menu.addAction("Insert Dummy Trade")
        act_dummy_trade.triggered.connect(self._insert_dummy_trade_for_current_user)

        menu.addSeparator()

        # 종료
        act_quit = menu.addAction("Quit")
        act_quit.setShortcut("Ctrl+Q" if os.name != "posix" else "Cmd+Q")
        act_quit.triggered.connect(self.close)

        self._apply_login_ui()

    def _toggle_login(self):
        if self.authApi.current_user:
            user = self.authApi.logout()
            self._apply_login_ui()
            QtWidgets.QMessageBox.information(self, "Logout", f"{user} 로그아웃")
        else:
            self._do_login()

    def _do_login(self):
        dlg = LoginDialog(self)
        if dlg.exec():
            user, pw = dlg.credentials()
            if self.authApi.login(user, pw):
                self._apply_login_ui()
                QtWidgets.QMessageBox.information(self, "Login", f"Welcome, {user}!")

                user_id = self.db.get_user_id_by_email(self.authApi.current_user)
                rows = self.db.get_working_orders_by_user(user_id, limit=100)
                self._load_trades_from_api()

            else:
                QtWidgets.QMessageBox.warning(self, "Login", "계정 정보가 올바르지 않습니다.")

    def _apply_login_ui(self):
        self.setWindowTitle(f"NASDAQ EXTENDED — {self.authApi.current_user or 'Logged out'}")
        self.act_login_logout.setText("Logout" if self.authApi.current_user else "Login…")

    def _open_account_dialog(self):
        dlg = OpenAccountDialog(self.db, self)
        dlg.exec()

    def _load_trades_from_db(self):
        user_id = self.authApi.current_user
        if not user_id:
            QtWidgets.QMessageBox.warning(self, "Login", "먼저 로그인하세요.")
            return
        trades = self.db.get_trades_by_user(user_id, limit=100)
        self.trades.render_from_db(trades)

    def _load_trades_from_api(self, api_url = "http://127.0.0.1:8000/"):
        # 1) JWT access_token 확인
        token = self.authApi.access_token
        if not token:
            QtWidgets.QMessageBox.warning(self, "Login", "먼저 로그인하세요.")
            return

        # 2) API 호출
        import requests

        try:
            url = f"{api_url}/trades/my?limit=100"
            headers = {
                "Authorization": f"Bearer {token}"
            }

            res = requests.get(url, headers=headers, timeout=5)

            if res.status_code != 200:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    f"/trades/my 조회 실패\nstatus={res.status_code}\n{res.text}"
                )
                return

            rows = res.json()  # list[TradeItem]
            # print(rows)

            # 3) 기존 테이블 렌더링 함수 그대로 사용
            self.trades.render_from_api(rows)

        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            return

    def _insert_dummy_trade_for_current_user(self):
        # 1) 로그인 체크
        if not self.authApi.current_user:
            QtWidgets.QMessageBox.warning(self, "Login", "먼저 로그인하세요.")
            return

        # 2) user_id 찾기
        user_email = self.authApi.current_user
        user_id = self.db.get_user_id_by_email(user_email)
        if user_id is None:
            QtWidgets.QMessageBox.warning(self, "DB", "현재 로그인한 사용자를 DB에서 찾을 수 없습니다.")
            return

        # 3) 계좌 하나 가져오기
        account_id = self.db.get_primary_account_id(user_id)
        if account_id is None:
            QtWidgets.QMessageBox.warning(self, "Account", "해당 사용자에 대한 계좌가 없습니다. 먼저 계좌를 개설하세요.")
            return

        # 4) 더미 체결 1건 삽입
        self.db.insert_dummy_trade(user_id, account_id)

        QtWidgets.QMessageBox.information(self, "Dummy Trade", "더미 체결 1건을 추가했습니다.")

        # 5) 그리고 DB에서 다시 읽어서 table_trades에 렌더링
        self._load_trades_from_api()

    def _refresh_orders_and_trades(self):
        if not self.authApi.current_user:
            self.ready_orders.render_from_db([])  # 미체결 비우기
            self.trades.render_from_db([])  # 체결 비우기 or 유지
            return

        user_id = self.authApi.current_user  #Eself.db.get_user_id_by_email(self.authApi.current_user)
        # 1) 미체결
        working = self.db.get_working_orders_by_user(user_id, limit=100)
        self.ready_orders.render_from_db(working)

        # 2) 체결 (전체 or 내 계정 기준)
        symbol = self.md.current_symbol()
        recent_trades = self.db.get_trades_by_user(user_id, limit=100)
        self.trades.render_from_db(recent_trades)

    def closeEvent(self, e):
        self.timer.stop()
        self.md.close()
        if hasattr(self, "db"):
            self.db.close()
        super().closeEvent(e)

    def _open_signup_dialog(self):
        from widgets.signup_dialog import SignupDialog
        dlg = SignupDialog(self.db, self)
        dlg.exec()


# 단독 실행용 (프로젝트에서 main.py가 따로 있으면 생략 가능)
if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(use_mock = False, base_price=20000.0)
    win.show()
    sys.exit(app.exec())
