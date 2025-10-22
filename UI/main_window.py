import sys, os, webbrowser
from pathlib import Path
from ib_insync import util
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
from tables import StockListTable, TradesTable
from ui.login_dialog import LoginDialog

class NasdaqWindow(QtWidgets.QMainWindow):
    def __init__(self, use_mock=False, base_price=20000.0):
        super().__init__()
        # 이 파일 위치 기준으로 resources 폴더 찾기
        RES_DIR = Path(__file__).resolve().parents[1] / "resources"
        ui_file = RES_DIR / "nasdaq_extended.ui"

        if not ui_file.exists():
            raise FileNotFoundError(f"UI file not found: {ui_file}")

        uic.loadUi(str(ui_file), self)

        self.setWindowTitle("NASDAQ EXTENDED")

        # 상태/컨트롤러
        self.auth = AuthController()
        self.md = MarketDataService(use_mock=use_mock, base_price=base_price)
        if not use_mock:
            self.md.start_ib()

        self.orderbook = OrderBookTable(self.table_hoga, row_count=21, base_index=10)
        self.stocklist = StockListTable(self.table_stocklist, rows=10)
        self.trades = TradesTable(self.table_trades, max_rows=30)

        self.ctrl = OrderBookController(self.md, self.orderbook, self.trades)

        # 버튼
        self.button_sell_market_price.clicked.connect(self._on_sell_mkt)
        self.button_buy_market_price.clicked.connect(self._on_buy_mkt)
        self.button_sell_fix_price.clicked.connect(self._on_sell_lmt)

        # 메뉴/로그인
        self._build_menu()

        # 타이머 (poll→render)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.ctrl.poll_and_render)
        self.timer.start(150)

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
        if ok: self.ctrl.sell_market(qty)

    def _on_buy_mkt(self):
        if not self._require_login(): return
        qty, ok = QtWidgets.QInputDialog.getInt(self, "시장가 매수", "수량:", 1, 1)
        if ok: self.ctrl.buy_market(qty)

    def _on_sell_lmt(self):
        if not self._require_login(): return
        qty, ok1 = QtWidgets.QInputDialog.getInt(self, "지정가 매도", "수량:", 1, 1)
        if not ok1: return
        px, ok2 = QtWidgets.QInputDialog.getDouble(self, "지정가 매도", "가격:", 0.0, 0, 1e12, 2)
        if not ok2 or px <= 0: return
        remain = self.ctrl.sell_limit(px, qty)
        if remain:
            QtWidgets.QMessageBox.information(self, "지정가", f"잔량 {remain} 대기 등록")

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
