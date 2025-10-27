import sys, os, webbrowser
from pathlib import Path
from ib_insync import util

from services.account_service import AccountService
from services.order_simulator import OrderSimulator
from widgets.balance_table import BalanceTable

util.useQt()

try:
    from PyQt6 import QtWidgets, uic
    from PyQt6.QtCore import QTimer, QUrl
    _QT6 = True
except Exception:
    from PyQt5 import QtWidgets, uic
    from PyQt5.QtCore import QTimer, QUrl
    _QT6 = False

from controllers.auth_controller import AuthController
from controllers.orderbook_controller import OrderBookController
from services.marketdata_service import MarketDataService
from widgets.orderbook_table import OrderBookTable
# from tables import StockListTable, TradesTable
from widgets.stocklist_table import StockListTable
from widgets.trades_table import TradesTable
from ui.login_dialog import LoginDialog

class NasdaqWindow(QtWidgets.QMainWindow):
    def __init__(self, use_mock=False, base_price=20000.0):
        super().__init__()
        # 이 파일 위치 기준으로 resources 폴더 찾기
        RES_DIR = Path(__file__).resolve().parents[1] / "resources"
        ui_file = RES_DIR / "nasdaq_extended.ui"
        initial_cash = float(os.getenv("INITIAL_CASH", "0"))

        if not ui_file.exists():
            raise FileNotFoundError(f"UI file not found: {ui_file}")

        uic.loadUi(str(ui_file), self)

        self.setWindowTitle("NASDAQ EXTENDED")

        # 상태/컨트롤러
        self.auth = AuthController()
        self.md = MarketDataService(use_mock=use_mock, base_price=base_price)
        self.account = AccountService()

        if not use_mock:
            self.md.start_ib()

        self.sim = OrderSimulator()
        self.orderbook = OrderBookTable(self.table_hoga, row_count=21, base_index=10)
        self.stocklist = StockListTable(self.table_stocklist, rows=10)
        self.trades = TradesTable(self.table_trades, max_rows=30)
        self._bind_balance_table()


        self.ctrl = OrderBookController(self.md, self.orderbook, self.trades, self.sim,balance_view = self.balance_table)

        # 버튼
        self.button_sell_market_price.clicked.connect(self._on_sell_mkt) #시장가 매수
        self.button_buy_market_price.clicked.connect(self._on_buy_mkt)   #시장가 매도
        self.button_sell_fix_price.clicked.connect(self._on_sell_lmt)    #지정가 매도

        # 메뉴/로그인
        self._build_menu()

        self.account = AccountService(initial_cash=initial_cash)


        # 타이머 (poll→render)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(150)

        self._bind_ready_orders_table()
        self._refresh_ready_orders_table()

    def _on_timer(self):
        self.ctrl.poll_and_render()
        self._refresh_ready_orders_table()
        self._bind_balance_table()

    def _bind_ready_orders_table(self):
        """
        QTabWidget(table_ready_trades) 안에 있는 QTableWidget(tap_ready_trades)을 찾아 바인딩.
        - 있으면 그대로 재사용
        - 없으면 첫 탭에 생성해서 붙임
        """
        tabw = getattr(self, "table_ready_trades", None)  # QTabWidget
        table = None

        if isinstance(tabw, QtWidgets.QTabWidget):
            # 1) objectName으로 정확히 찾기 (ui의 이름이 tap_ready_trades라면 그대로 사용)
            table = tabw.findChild(QtWidgets.QTableWidget, "tap_ready_trades")
            if table is None:
                # 2) 다른 이름으로 되어 있을 수 있으니 백업 탐색
                table = tabw.findChild(QtWidgets.QTableWidget, "table_ready_trades") \
                        or next(iter(tabw.findChildren(QtWidgets.QTableWidget)), None)

            if table is None:
                # 3) 테이블이 없다면 첫 번째 탭에 생성해서 붙이기
                if tabw.count() == 0:
                    # 빈 QTabWidget이면 탭 컨테이너부터 만든다
                    container = QtWidgets.QWidget()
                    container.setObjectName("tab_ready_trades_container")
                    tabw.addTab(container, "미체결")
                else:
                    container = tabw.widget(0)

                if container.layout() is None:
                    container.setLayout(QtWidgets.QVBoxLayout(container))

                table = QtWidgets.QTableWidget(container)
                table.setObjectName("tap_ready_trades")  # .ui에서 쓰는 이름과 맞춰두기
                container.layout().addWidget(table)

        else:
            # 안전장치: 혹시 .ui에서 탭이 아니라 루트에 테이블만 있는 경우
            table = getattr(self, "tap_ready_trades", None)
            if table is None:
                table = QtWidgets.QTableWidget(self)
                table.setObjectName("tap_ready_trades")
                # 필요하면 적당한 위치에 붙이세요(예: 중앙 위젯 등)

        # 최종 바인딩
        self.tap_ready_trades = table
        self._init_ready_orders_table(self.tap_ready_trades)

    def _init_ready_orders_table(self, t: QtWidgets.QTableWidget):
        """미체결 테이블 헤더/속성 초기화"""
        t.setColumnCount(7)
        # t.setHorizontalHeaderLabels(["시간", "주문ID", "종류", "Side", "가격", "수량", "상태"])
        t.verticalHeader().setVisible(False)
        # 읽기 전용 & 행 단위 선택
        if hasattr(QtWidgets.QAbstractItemView, "EditTrigger"):
            t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        else:
            t.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        t.horizontalHeader().setStretchLastSection(True)

    def _refresh_ready_orders_table(self):
        """_working_orders → table_ready_trades 렌더링"""
        if not hasattr(self, "tap_ready_trades"):
            return
        t = self.tap_ready_trades
        rows = self.ctrl.sim.working or []

        t.setRowCount(len(rows))
        for r, od in enumerate(rows):
            # 안전하게 기본값
            # time = od.get("time", "")
            # oid = od.get("id", "")
            # otype = od.get("type", "LMT")
            # side = od.get("side", "")
            # price = od.get("price", 0.0)
            # qty = od.get("qty", 0)
            # stat = od.get("status", "WORKING")
            time = getattr(od, "time", "")
            oid = getattr(od, "id", "")
            otype = getattr(od, "type", "LMT")
            side = getattr(od, "side", "")
            price = getattr(od, "price", 0.0)
            qty = getattr(od, "qty", 0)
            stat = getattr(od, "status", "WORKING")

            t.setItem(r, 0, QtWidgets.QTableWidgetItem(str(time)))
            t.setItem(r, 1, QtWidgets.QTableWidgetItem(str(oid)))
            t.setItem(r, 2, QtWidgets.QTableWidgetItem(str(otype)))
            t.setItem(r, 3, QtWidgets.QTableWidgetItem(str(side)))
            t.setItem(r, 4, QtWidgets.QTableWidgetItem(f"{float(price):,.2f}"))
            t.setItem(r, 5, QtWidgets.QTableWidgetItem(str(int(qty))))
            t.setItem(r, 6, QtWidgets.QTableWidgetItem(str(stat)))

            t.resizeColumnsToContents()

    def _bind_balance_table(self):
        """
        table_ready_trades(QTabWidget)에 '잔고' 탭을 붙이고
        그 안의 QTableWidget을 BalanceTable로 래핑.
        """
        tabw = getattr(self, "tab_balance_table", None)
        if not isinstance(tabw, QtWidgets.QTabWidget):
            # 안전장치: 탭이 없다면 루트에 하나 생성해서 달아도 됨
            container = QtWidgets.QWidget(self)
            layout = QtWidgets.QVBoxLayout(container)
            table = QtWidgets.QTableWidget(container)
            layout.addWidget(table)
            self.setCentralWidget(container)  # 필요 시 배치 조정
            self.balance_table = BalanceTable(table)
            return

        # '잔고' 탭 찾기/생성
        # objectName이 있으면 사용하고, 없으면 첫 생성
        balance_tab = None
        for i in range(tabw.count()):
            if tabw.tabText(i) == "잔고":
                balance_tab = tabw.widget(i)
                break
        if balance_tab is None:
            balance_tab = QtWidgets.QWidget()
            balance_tab.setObjectName("tab_balance_table")
            balance_tab.setLayout(QtWidgets.QVBoxLayout(balance_tab))
            tabw.addTab(balance_tab, "잔고")

        # 테이블 찾기/생성
        table = balance_tab.findChild(QtWidgets.QTableWidget, "tab_balance_table")
        if table is None:
            table = QtWidgets.QTableWidget(balance_tab)
            table.setObjectName("tab_balance_table")
            balance_tab.layout().addWidget(table)

        # 래퍼 생성
        self.balance_table = BalanceTable(table)
        # 초기 렌더
        self.balance_table.render(self.account.state)

    # --------- 주문 버튼 핸들러 -----------
    def _require_login(self) -> bool:
        if self.auth.current_user:
            return True
        QtWidgets.QMessageBox.warning(self, "Login", "먼저 로그인하세요.")
        self._do_login()
        return bool(self.auth.current_user)

    def _on_sell_mkt(self):
        if not self._require_login(): return
        qty, ok = QtWidgets.QInputDialog.getInt(self, "시장가 매도", "수량:", 1, 1)
        if ok:
            self.ctrl.sell_market(qty)
            self._refresh_ready_orders_table()


    def _on_buy_mkt(self):
        if not self._require_login(): return
        qty, ok = QtWidgets.QInputDialog.getInt(self, "시장가 매수", "수량:", 1, 1)
        if ok:
            self.ctrl.buy_market(qty)
            self._refresh_ready_orders_table()

    def _on_sell_lmt(self):
        if not self._require_login(): return
        qty, ok1 = QtWidgets.QInputDialog.getInt(self, "지정가 매도", "수량:", 1, 1)
        if not ok1: return
        px, ok2 = QtWidgets.QInputDialog.getDouble(self, "지정가 매도", "가격:", 0.0, 0, 1e12, 2)
        if not ok2 or px <= 0: return
        remain = self.ctrl.sell_limit(px, qty)
        if remain:
            self._refresh_ready_orders_table()
            QtWidgets.QMessageBox.information(self, "지정가", f"잔량 {remain} 대기 등록")
            print(len(self.ctrl.sim.working))
            print(self.ctrl.sim.working)


    # --------- 메뉴/로그인 -----------
    def _build_menu(self):
        mb = self.menuBar()
        try: mb.setNativeMenuBar(False)
        except: pass
        menu = mb.addMenu("File")
        self.act_login_logout = menu.addAction("Login…")
        self.act_login_logout.setShortcut("Ctrl+L" if sys.platform != "darwin" else "Cmd+L")
        self.act_login_logout.triggered.connect(self._toggle_login)
        menu.addSeparator()
        act_quit = menu.addAction("Quit")
        act_quit.setShortcut("Ctrl+Q" if sys.platform != "darwin" else "Cmd+Q")
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

    # 종료 처리
    def closeEvent(self, e):
        self.timer.stop()
        self.md.close()
        super().closeEvent(e)
