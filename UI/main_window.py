# MainWindows.py
import os
from pathlib import Path

from ib_insync import util
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
from controllers.orderbook_controller import OrderBookController
from services.marketdata_service import MarketDataService
from services.order_simulator import OrderSimulator
from services.account_service import AccountService

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


        # --- 상태/서비스 초기화 ---
        self.auth = AuthController()

        initial_cash = float(os.getenv("INITIAL_CASH", "0"))
        self.account = AccountService(initial_cash=initial_cash)

        self.md = MarketDataService(use_mock=use_mock, provider="BINANCE", symbol="solusdt", rows=10,)
        # if not use_mock:
        #     self.md.start_ib()
        # self.md.start_binance()
        if not use_mock:
            self.md.start_oracle()

        self.sim = OrderSimulator()

        self._bind_symbol_selector()
        # --- 위젯 래퍼 바인딩 ---
        self.orderbook = OrderBookTable(self.table_hoga, row_count=21, base_index=10)
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
            balance_table=self.balance_table
        )

        # --- 버튼 핸들러 연결 ---
        # 주의: UI의 오브젝트명이 정확히 아래와 같아야 합니다.
        # button_sell_market_price (시장가 매도), button_buy_market_price (시장가 매수), button_sell_fix_price (지정가 매도)
        self.button_sell_market_price.clicked.connect(self._on_sell_mkt)
        self.button_buy_market_price.clicked.connect(self._on_buy_mkt)
        self.button_sell_fix_price.clicked.connect(self._on_sell_lmt)

        # --- 메뉴/로그인 ---
        self._build_menu()

        # --- 타이머: 시세 폴링 및 UI 반영 ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(150)

        # 초기 렌더
        self.ready_orders.render(self.sim.working)
        self.balance_table.render(self.account.state)

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

        # md에 반영(오라클/피드 재시작 등)
        if hasattr(self.md, "set_symbol"):
            # 바이낸스는 보통 소문자 사용 -> 정규화해서 전달
            norm = sym.lower()
            self.md.set_symbol(norm)

            # 심볼 변경 시 구독/스트림 재시작이 필요하면 수행
            # 구현되어 있는 메서드에 맞춰 아래 중 하나가 존재한다면 호출
            if hasattr(self.md, "restart_oracle"):
                self.md.restart_oracle()
            elif hasattr(self.md, "start_oracle"):
                # 간단히 다시 시작 (내부에서 이미 닫고 다시 열도록 구현돼 있으면 더 깔끔)
                self.md.start_oracle()
            elif hasattr(self.md, "restart"):
                self.md.restart()

        # 화면 초기화
        self.ctrl.last_depth = None
        try:
            self.orderbook.set_orderbook([], [], 0.0)
        except Exception:
            pass
        if hasattr(self.trades, "trades"):
            self.trades.trades.clear()
            self.trades._render()

        # 바로 한 번 렌더 유도 (다음 타이머 틱까지 기다리지 않게)
        try:
            self.ctrl.poll_and_render()
        except Exception:
            pass

        # 타이틀
        self.setWindowTitle(f"NASDAQ EXTENDED — {self.auth.current_user or 'Logged out'} — {sym}")

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

    # --------------------------
    # 타이머/버튼/로그인
    # --------------------------
    def _on_timer(self):
        self.ctrl.poll_and_render()
        self.ready_orders.render(self.sim.working)  # 미체결 갱신

    def _require_login(self) -> bool:
        if self.auth.current_user:
            return True
        QtWidgets.QMessageBox.warning(self, "Login", "먼저 로그인하세요.")
        self._do_login()
        return bool(self.auth.current_user)

    def _on_sell_mkt(self):
        if not self._require_login():
            return
        qty, ok = QtWidgets.QInputDialog.getInt(self, "시장가 매도", "수량:", 1, 1)
        if ok:
            self.ctrl.sell_market(qty)
            self.ready_orders.render(self.sim.working)

    def _on_buy_mkt(self):
        if not self._require_login():
            return
        qty, ok = QtWidgets.QInputDialog.getInt(self, "시장가 매수", "수량:", 1, 1)
        if ok:
            self.ctrl.buy_market(qty)
            self.ready_orders.render(self.sim.working)

    def _on_sell_lmt(self):
        if not self._require_login():
            return
        qty, ok1 = QtWidgets.QInputDialog.getInt(self, "지정가 매도", "수량:", 1, 1)
        if not ok1:
            return
        px, ok2 = QtWidgets.QInputDialog.getDouble(self, "지정가 매도", "가격:", 0.0, 0, 1e12, 2)
        if not ok2 or px <= 0:
            return
        remain = self.ctrl.sell_limit(px, qty)
        self.ready_orders.render(self.sim.working)
        if remain:
            QtWidgets.QMessageBox.information(self, "지정가", f"잔량 {remain} 대기 등록")

    def _build_menu(self):
        mb = self.menuBar()
        try:
            mb.setNativeMenuBar(False)
        except Exception:
            pass

        menu = mb.addMenu("File")
        self.act_login_logout = menu.addAction("Login…")
        self.act_login_logout.setShortcut("Ctrl+L" if os.name != "posix" else "Cmd+L")
        self.act_login_logout.triggered.connect(self._toggle_login)

        menu.addSeparator()
        act_quit = menu.addAction("Quit")
        act_quit.setShortcut("Ctrl+Q" if os.name != "posix" else "Cmd+Q")
        act_quit.triggered.connect(self.close)
        self._apply_login_ui()

    def _toggle_login(self):
        if self.auth.current_user:
            user = self.auth.logout()
            self._apply_login_ui()
            QtWidgets.QMessageBox.information(self, "Logout", f"{user} 로그아웃")
        else:
            self._do_login()

    def _do_login(self):
        dlg = LoginDialog(self)
        if dlg.exec():
            user, pw = dlg.credentials()
            if self.auth.login(user, pw):
                self._apply_login_ui()
                QtWidgets.QMessageBox.information(self, "Login", f"Welcome, {user}!")
            else:
                QtWidgets.QMessageBox.warning(self, "Login", "계정 정보가 올바르지 않습니다.")

    def _apply_login_ui(self):
        self.setWindowTitle(f"NASDAQ EXTENDED — {self.auth.current_user or 'Logged out'}")
        self.act_login_logout.setText("Logout" if self.auth.current_user else "Login…")

    def closeEvent(self, e):
        self.timer.stop()
        self.md.close()
        super().closeEvent(e)


# 단독 실행용 (프로젝트에서 main.py가 따로 있으면 생략 가능)
if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(use_mock = False, base_price=20000.0)
    win.show()
    sys.exit(app.exec())
