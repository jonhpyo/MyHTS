# app.py
from __future__ import annotations

import os
import random
import sys
import webbrowser

import yfinance as yf
from ib_insync import util
util.useQt()

# from PyQt5.QtWidgets import QTableWidget, QDockWidget
# from PyQt5 import QtWidgets, uic
# from PyQt5.QtCore import QTimer, QUrl
# from PySide6.QtWebEngineWidgets import QWebEngineView
from dotenv import load_dotenv
from ib_insync import IB, Future

from widgets.orderbook_table import OrderBookTable

# --- Simple Login Dialog (PyQt6/5 compatible) -----------------------------
try:
    from PyQt6 import QtWidgets
    from PyQt6.QtCore import Qt
    _QT6 = True
except Exception:
    from PyQt5 import QtWidgets
    from PyQt5.QtCore import Qt
    _QT6 = False

load_dotenv()
# ✅ macOS WebEngine 크래시 방지 권장
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

# ✅ PyQt6 우선, 실패 시 PyQt5로 폴백 (uic, QTimer, QUrl도 함께)
try:
    from PyQt6 import QtWidgets, uic
    from PyQt6.QtCore import QTimer, QUrl
    QT_LIB = "PyQt6"
except Exception:
    from PyQt5 import QtWidgets, uic
    from PyQt5.QtCore import QTimer, QUrl
    QT_LIB = "PyQt5"
from tables import StockListTable, TradesTable

# from adapters.kiwoom import KiwoomSource as DataSource

USE = os.getenv("DATA_SOURCE", "ALPACA")
if USE.upper() == "ALPACA":
    pass
# elif USE.upper() == "NASDAQ":
#     from adapters.nq_polygon_pygt import
else:
    pass

class NasdaqWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("nasdaq_extended.ui", self)
        self.setWindowTitle("NASDAQ EXTENDED (모의 API)")

        self._current_user = None  # ← 로그인 상태 저장
        self._account_menu = None  # ← File 메뉴 핸들
        self.act_login_logout = None  # ← Login/Logout 토글 액션

        self._build_menubar()

        self.orderbook = OrderBookTable(self.table_hoga, row_count=21, base_index=10)
        self.stocklist = StockListTable(self.table_stocklist, rows=10)
        self.trades = TradesTable(self.table_trades, max_rows=30)

        # self.orderbook.populate()
        # self.stocklist.populate()
        # self.trades.populate(initial_count=5)

        self._pending = None
        self._last_depth = None  # 최신 호가 스냅샷 저장 (bids, asks, mid)
        self._working_orders = []  # 대기중(미체결) 지정가 주문들 저장

        self.button_chart.clicked.connect(self.open_chart_window)
        self.button_sell_market_price.clicked.connect(self.on_sell_market_clicked)
        self.button_buy_market_price.clicked.connect(self.on_buy_market_clicked)
        self.button_sell_fix_price.clicked.connect(self.on_sell_limit_clicked)

        def on_depth(bids, asks, mid):
            self._pending = (bids, asks, mid)


        # ✅ .env 사용 (루트에 POLYGON_API_KEY=... 넣기)
        POLYGON_API_KEY = "VvrUY_6J_R8G16U2zXekn0FBGcWL7DpM"
        load_dotenv()
        USE_MOCK_DATA = os.getenv("USE_MOCK_DATA")

        if not POLYGON_API_KEY:
            raise RuntimeError("POLYGON_API_KEY가 .env에 없습니다.")

        # ❗폴리곤 선물 티커는 계정 문서 기준으로 정확히 넣어야 합니다.
        #   예) 연속계약: "@NQ"  / 특정월물: "CME:NQZ2025" (계정마다 표기 다를 수 있음)
        FUTURE_TICKERS = ["AAPL", "MSFT", "GOOG"]

        # self.bridge = PolygonWSBridge(
        #     api_key=POLYGON_API_KEY,
        #     tickers=FUTURE_TICKERS,
        #     on_depth=on_depth,
        #     url="wss://socket.polygon.io/futures",
        # )
        # self.bridge = PolygonWSBridge(
        #     api_key=POLYGON_API_KEY,
        #     tickers=FUTURE_TICKERS,
        #     on_depth=on_depth,
        #     url="wss://socket.polygon.io/stocks",
        # )
        # Databento로 NQ.FUT Top-of-Book
        # self.db_bridge = DatabentoBridge(
        #     on_depth=on_depth,
        #     dataset="GLBX.MDP3",
        #     schema="tbbo",  # ← 수정됨
        #     symbols="NQ.FUT",  # 예: ES.FUT, MNQ.FUT 등
        #     stype_in="parent",
        # )
        self.ib = IB()
        self.ib.connect('127.0.0.1', 7497, clientId=100)
        self.ib.reqMarketDataType(1)

        contract = Future('NQ', '202512', 'CME')
        self.ib.qualifyContracts(contract)
        self.ticker = self.ib.reqMktDepth(contract, numRows=10)

        def get_last_close(symbol="NQ=F"):
            data = yf.download(symbol, period="2d", interval="1d")
            return float(data["Close"].iloc[-1])

        BASE_PRICE = get_last_close("NQ=F")

        # Qt 타이머에서 depth 꺼내 화면 반영
        def pump():
            if USE_MOCK_DATA:
                bids = [(BASE_PRICE - i * 2 - random.random(), random.randint(1, 5), 1) for i in range(10)]
                asks = [(BASE_PRICE + i * 2 + random.random(), random.randint(1, 5), 1) for i in range(10)]
                mid = (bids[0][0] + asks[0][0]) / 2
                self._pending = (bids, asks, mid)
                return

            if not getattr(self, "ticker", None):
                return
            bids = [(float(r.price), int(r.size or 0), 1) for r in self.ticker.domBids if r.price is not None]
            asks = [(float(r.price), int(r.size or 0), 1) for r in self.ticker.domAsks if r.price is not None]

            if not bids and not asks:
                return

            mid = None
            if bids and asks:
                mid = (bids[0][0] + asks[0][0]) / 2.0
            elif bids:
                mid = bids[0][0]
            elif asks:
                mid = asks[0][0]

            self._pending = (bids, asks, mid)

        # ✅ pump용 타이머 (데이터 수집)
        self.timer_data = QTimer(self)
        self.timer_data.timeout.connect(pump)
        self.timer_data.start(150)  # 100~250ms 권장

        # ✅ 렌더용 타이머 (화면 반영)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._flush_depth_to_ui)
        self.timer.start(150)



    # def _flush(self):
    #     pending = getattr(self, "_pending", None)
    #     if not pending:
    #         return
    #     bids, asks, mid = pending
    #     self._pending = None
    #     self.orderbook.set_orderbook(bids=bids, asks=asks, mid_price=mid)

    # def _flush(self):
    #     if not self._pending:
    #         return
    #     bids, asks, mid = self._pending
    #     self._pending = None
    #     self.orderbook.set_orderbook(bids=bids, asks=asks, mid_price=mid)


    def on_sell_market_clicked(self):
        """시장가 매도 시뮬: 입력 수량을 현재 매수호가에 순차 체결하고, 호가/체결창을 갱신"""
        if not self._require_login():
            return

        # 수량 입력
        qty, ok = QtWidgets.QInputDialog.getInt(self, "시장가 매도", "수량(계약):", value=1, min=1)
        if not ok or qty <= 0:
            return

        if not getattr(self, "_last_depth", None):
            QtWidgets.QMessageBox.warning(self, "호가 없음", "현재 호가가 없습니다. 잠시 후 다시 시도하세요.")
            return

        bids, asks, mid = self._last_depth
        if not bids:
            QtWidgets.QMessageBox.warning(self, "체결 불가", "매수호가가 없어 시장가 매도가 불가합니다.")
            return

        # 체결: bids 위에서부터 소비
        remaining = qty
        fills = []  # (price, filled_qty)
        new_bids = []
        for price, level_qty, _lvl in bids:
            if remaining <= 0:
                new_bids.append((price, level_qty, _lvl))
                continue
            if level_qty <= 0:
                new_bids.append((price, level_qty, _lvl))
                continue

            take = min(level_qty, remaining)
            fills.append((price, take))
            remaining -= take
            leftover = level_qty - take
            new_bids.append((price, leftover, _lvl))

        if remaining > 0:
            # 전부 못 팔았으면 알림 (부분체결만 됨)
            QtWidgets.QMessageBox.information(
                self, "부분체결", f"요청 {qty} 중 {qty - remaining}만 체결되었습니다."
            )

        # 평균 체결가 계산(가중평균)
        total_filled = sum(q for _, q in fills)
        if total_filled == 0:
            return
        vwap = sum(p * q for p, q in fills) / total_filled

        # 체결(매도) → 체결창에 기록(빨간/파랑 플래그는 기존 규칙: up=True면 빨간)
        # 매도는 가격이 내려갔다고 보기 어려우니, 최근 미드/이전 가격과 비교가 없으니 up=False로 넣음(파랑)
        # 원하시면 up=True로 바꾸세요.
        self._append_trade_row(price=vwap, qty=total_filled, up=False)

        # 호가창 잔량 반영: 0이하 레벨은 0으로 두고 그대로 표시
        # mid는 best bid/ask가 있으면 다시 산출
        best_bid = next((p for p, q, _ in new_bids if q > 0), None)
        best_ask = asks[0][0] if asks else None
        new_mid = mid
        if best_bid is not None and best_ask is not None:
            new_mid = (best_bid + best_ask) / 2.0
        elif best_bid is not None:
            new_mid = best_bid
        elif best_ask is not None:
            new_mid = best_ask

        # 내부 상태/화면 갱신
        self._last_depth = (new_bids, asks, new_mid)
        self.orderbook.set_orderbook(bids=new_bids, asks=asks, mid_price=new_mid)

        # 완료 메시지
        QtWidgets.QMessageBox.information(
            self, "시장가 매도",
            f"시장가 매도 체결\n- 수량: {total_filled}\n- 평균가: {vwap:,.2f}"
        )

    def on_buy_market_clicked(self):
        # 1) 로그인 필수라면 가드 (선택)
        if hasattr(self, "_require_login") and not self._require_login():
            return

        # 2) 최신 호가 확인
        if not self._last_depth:
            QtWidgets.QMessageBox.warning(self, "No depth", "호가를 아직 받지 못했습니다.")
            return

        qty = max(1, int(self._get_order_qty()))
        bids, asks, mid = self._last_depth

        if not asks:
            QtWidgets.QMessageBox.warning(self, "No liquidity", "매도호가가 없습니다.")
            return

        remaining = qty
        filled = 0
        cost = 0.0
        new_asks = []

        # asks: [(price, size, level), ...]  가장 좋은 가격이 앞이라고 가정
        for (px, sz, lv) in asks:
            if remaining <= 0:
                new_asks.append((px, sz, lv))
                continue
            take = min(sz, remaining)
            filled += take
            cost += px * take
            left = sz - take
            remaining -= take
            if left > 0:
                new_asks.append((px, left, lv))

        if filled == 0:
            QtWidgets.QMessageBox.information(self, "No fill", "체결이 발생하지 않았습니다.")
            return

        vwap = cost / filled

        # 새 미드 계산 (남은 최우선호가 기준)
        top_bid = bids[0][0] if bids else None
        top_ask = new_asks[0][0] if new_asks else None
        if top_bid is not None and top_ask is not None:
            new_mid = (top_bid + top_ask) / 2.0
        elif top_bid is not None:
            new_mid = float(top_bid)
        elif top_ask is not None:
            new_mid = float(top_ask)
        else:
            new_mid = mid

        # 5) 스냅샷/화면 갱신
        self._last_depth = (bids, new_asks, new_mid)
        self.orderbook.set_orderbook(bids=bids, asks=new_asks, mid_price=new_mid)

        # 6) 체결 안내
        QtWidgets.QMessageBox.information(
            self, "시장가 매수 체결",
            f"수량: {filled}\nVWAP: {vwap:,.2f}\n미체결: {remaining}"
        )

        # (선택) 체결 내역 테이블/로그 추가가 필요하면 여기에 작성
        # 예: self.trades.prepend_trade(time_str, vwap, filled, up=True)

    def on_sell_limit_clicked(self):
        if not self._require_login():
            return

        if not self._last_depth:
            QtWidgets.QMessageBox.warning(self, "호가 없음", "현재 호가 데이터를 받지 못했습니다.")
            return

        # 수량/가격 읽기
        qty = self._get_order_qty()  # 없으면 1로 처리하는 헬퍼 (아래 6) 참고)
        price = self._get_limit_price()  # 스핀박스/라인에디트 or 입력창 (아래 6) 참고)
        if price is None:
            return

        bids, asks, mid = self._last_depth
        if not bids:
            # 매수호가가 없으면 대기로 저장
            self._working_orders.append({"side": "SELL", "price": price, "qty": qty, "type": "LMT"})
            QtWidgets.QMessageBox.information(self, "지정가 매도", f"{price:.2f} / {qty}주 대기(미체결)로 등록했습니다.")
            return

        best_bid = float(bids[0][0])

        if price <= best_bid:
            # ✅ 즉시 체결: 매수호가를 먹으면서 체결
            filled, vwap = self._fill_against_bids(price_limit=price, qty=qty, bids=bids)
            if filled > 0:
                self.trades.add_fill("SELL", vwap, filled)  # 체결내역 테이블에 기록
                remain = qty - filled
                msg = f"지정가 매도 체결: {filled} @ {vwap:.2f}"
                if remain > 0:
                    msg += f" / 잔량 {remain} 대기"
                    # 잔량은 대기 주문으로 남김
                    self._working_orders.append({"side": "SELL", "price": price, "qty": remain, "type": "LMT"})
                QtWidgets.QMessageBox.information(self, "지정가 매도", msg)
            else:
                # 이론상 오기 힘듦: 방어
                self._working_orders.append({"side": "SELL", "price": price, "qty": qty, "type": "LMT"})
                QtWidgets.QMessageBox.information(self, "지정가 매도", f"{price:.2f} / {qty}주 대기(미체결)로 등록했습니다.")
        else:
            # ✅ 대기(미체결): 매수호가가 지정가보다 낮음 → 올라오면 체결
            self._working_orders.append({"side": "SELL", "price": price, "qty": qty, "type": "LMT"})
            QtWidgets.QMessageBox.information(self, "지정가 매도", f"{price:.2f} / {qty}주 대기(미체결)로 등록했습니다.")


    def _append_trade_row(self, price: float, qty: int, up: bool):
        """
        TradesTable은 public 추가 메서드가 없어서 내부 리스트에 직접 append 후 _render 호출.
        (tables.TradesTable 구현 기준)
        """
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")
        # self.trades.trades: List[Dict] 에 직접 추가 (최신이 맨 위)
        self.trades.trades.insert(0, {"time": now, "price": round(price, 2), "qty": int(qty), "up": bool(up)})
        # 최대 행 수 유지
        if len(self.trades.trades) > self.trades.max_rows:
            self.trades.trades = self.trades.trades[: self.trades.max_rows]
        # 리프레시
        self.trades._render()

    def open_chart_window(self):
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
        url_text = "https://www.tradingview.com/chart/?symbol=CME_MINI%3ANQ1%21"

        # 1) WebEngine 가용성 확인 (PyQt6 → PyQt5)
        WebEngineView, QUrlType = None, None

        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtCore import QUrl as QUrl6
            WebEngineView, QUrlType = QWebEngineView, QUrl6
            qt = "qt6"
        except ImportError:
            try:
                from PyQt5.QtWebEngineWidgets import QWebEngineView
                from PyQt5.QtCore import QUrl as QUrl5
                WebEngineView, QUrlType = QWebEngineView, QUrl5
                qt = "qt5"
            except ImportError:
                import webview
                webview.create_window(
                    "해외선물 차트 (TradingView)",
                    "https://www.tradingview.com/chart/?symbol=CME_MINI%3ANQ1%21"
                )
                webview.start()
                return

        if WebEngineView is None:
            # WebEngine 불가 → 외부 브라우저로 열기 (dock 불가)
            webbrowser.open(url_text)
            return

        # 2) Dock 생성
        dock = self._make_chart_dock(title=f"해외선물 차트 (TradingView, {qt.upper()})")

        # 3) WebEngineView 장착
        view = WebEngineView(dock)
        view.load(QUrlType(url_text))
        dock.setWidget(view)

        # 4) 도킹 위치 지정 및 탭화
        area = self._dock_area_right()
        self.addDockWidget(area, dock)

        # 이미 차트 도크가 있다면 탭 형태로 묶기
        if not hasattr(self, "_chart_docks"):
            self._chart_docks = []
        if self._chart_docks:
            self.tabifyDockWidget(self._chart_docks[-1], dock)
        self._chart_docks.append(dock)

        dock.show()

    def _make_chart_dock(self, title: str):
        # PyQt5/6 호환 import
        try:
            from PyQt6.QtWidgets import QDockWidget
            from PyQt6.QtCore import Qt
            DockWidgetClosable   = Qt.DockWidgetFeature.DockWidgetClosable
            DockWidgetMovable    = Qt.DockWidgetFeature.DockWidgetMovable
            DockWidgetFloatable  = Qt.DockWidgetFeature.DockWidgetFloatable
        except Exception:
            from PyQt5.QtWidgets import QDockWidget
            from PyQt5.QtCore import Qt
            DockWidgetClosable   = Qt.DockWidgetClosable
            DockWidgetMovable    = Qt.DockWidgetMovable
            DockWidgetFloatable  = Qt.DockWidgetFloatable

        dock = QDockWidget(title, self)
        dock.setObjectName(f"ChartDock_{len(getattr(self, '_chart_docks', [])) + 1}")
        dock.setFeatures(DockWidgetClosable | DockWidgetMovable | DockWidgetFloatable)
        dock.setFloating(False)  # 처음에는 플로팅 상태로 띄우고, 사용자가 드래그로 붙일 수 있게
        dock.setMinimumSize(500, 350)
        return dock


    def _dock_area_right(self):
        """PyQt5/6 호환 도킹 영역 반환 (기본: RightDockWidgetArea)."""
        try:
            from PyQt6.QtCore import Qt
            return Qt.DockWidgetArea.RightDockWidgetArea
        except Exception:
            from PyQt5.QtCore import Qt
            return Qt.RightDockWidgetArea

    def _build_menubar(self):
        mb = self.menuBar()
        try:
            mb.setNativeMenuBar(False)  # macOS에서도 창 내부 표시
        except Exception:
            pass

        # File 메뉴
        self._account_menu = mb.addMenu("File")

        # ▼ Login/Logout 토글 액션(항상 맨 위)
        self.act_login_logout = self._account_menu.addAction("Login…")
        self.act_login_logout.setShortcut("Ctrl+L" if sys.platform != "darwin" else "Cmd+L")
        self.act_login_logout.triggered.connect(self._toggle_login_logout)

        self._account_menu.addSeparator()

        # Quit
        act_quit = self._account_menu.addAction("Quit")
        act_quit.setShortcut("Ctrl+Q" if sys.platform != "darwin" else "Cmd+Q")
        act_quit.triggered.connect(self.close)

        # 초기 ui 반영
        self._apply_login_ui()

    def _action_login(self):
        dlg = LoginDialog(self)
        while True:
            result = dlg.exec()
            accepted = (
                result == (QtWidgets.QDialog.DialogCode.Accepted
                           if hasattr(QtWidgets.QDialog, "DialogCode")
                           else QtWidgets.QDialog.Accepted)
            )
            if not accepted:
                return

            user, pw = dlg.credentials()

            # ---------- 아주 단순한 더미 검증 ----------
            valid = (user in {"demo", "paper"}) and (pw == "1234")

            if not valid:
                dlg.lbl_error.setText("Invalid ID or password. (try: demo / 1234)")
                continue

            self._current_user = user
            QtWidgets.QMessageBox.information(self, "Login", f"Welcome, {user}!")
            # 로그인 후 ui 반영(타이틀/버튼 enable 등)
            self._apply_login_ui()
            return

    def _apply_login_ui(self):
        who = self._current_user or "Logged out"
        self.setWindowTitle(f"NASDAQ EXTENDED — {who}")
        # 로그인 필요 기능이 있으면 여기서 enable/disable
        # 예) self.button_chart.setEnabled(self._current_user is not None)

    def _toggle_login_logout(self):
        """메뉴 클릭 시: 로그인 상태면 로그아웃, 로그아웃 상태면 로그인 다이얼로그."""
        if self._current_user:
            # --- 로그아웃 ---
            user = self._current_user
            self._current_user = None
            self._apply_login_ui()
            QtWidgets.QMessageBox.information(self, "Logout", f"{user}님이 로그아웃되었습니다.")
        else:
            # --- 로그인 다이얼로그 ---
            dlg = LoginDialog(self)
            while True:
                result = dlg.exec()
                accepted = (
                    result == (QtWidgets.QDialog.DialogCode.Accepted
                               if hasattr(QtWidgets.QDialog, "DialogCode")
                               else QtWidgets.QDialog.Accepted)
                )
                if not accepted:
                    return
                user, pw = dlg.credentials()
                # 데모 검증 (원하면 실제 검증으로 교체)
                valid = (user in {"demo", "paper"}) and (pw == "1234")
                if not valid:
                    dlg.lbl_error.setText("Invalid ID or password. (try: demo / 1234)")
                    continue
                self._current_user = user
                self._apply_login_ui()
                QtWidgets.QMessageBox.information(self, "Login", f"Welcome, {user}!")
                return

    def _apply_login_ui(self):
        """타이틀/메뉴 텍스트 등 상태 반영."""
        who = self._current_user or "Logged out"
        self.setWindowTitle(f"NASDAQ EXTENDED — {who}")

        # 메뉴 텍스트 토글
        if self.act_login_logout:
            self.act_login_logout.setText("Logout" if self._current_user else "Login…")

        # 로그인 필요 버튼/액션 토글 예시
        # self.button_chart.setEnabled(self._current_user is not None)

    def _require_login(self) -> bool:
        """보호 기능 가드."""
        if self._current_user:
            return True
        QtWidgets.QMessageBox.warning(self, "Login required", "먼저 로그인하세요.")
        self._toggle_login_logout()  # 로그인 다이얼로그 띄움
        return self._current_user is not None

    def _flush_depth_to_ui(self):
        """버퍼→OrderBookTable 반영 + 최근 호가 저장"""
        if not self._pending:
            return
        bids, asks, mid = self._pending
        self._pending = None

        # 화면 반영
        self.orderbook.set_orderbook(bids=bids, asks=asks, mid_price=mid)

        # ✅ 최신 호가 스냅샷 저장
        self._last_depth = (bids, asks, mid)

        # ✅ 대기중 지정가 주문 자동 매칭 시도
        self._match_working_orders()

    def _match_working_orders(self):
        if not self._working_orders or not self._last_depth:
            return
        bids, asks, mid = self._last_depth

        # 호가를 로컬 복사본으로 사용 (체결 시 사이즈 차감 시뮬)
        local_bids = [{"price": float(p), "size": int(sz)} for (p, sz, *_rest) in bids]

        remain_orders = []
        for od in self._working_orders:
            side = od["side"].upper()
            qty = int(od["qty"])
            px = float(od["price"])

            if side == "SELL":
                filled_total = 0
                notional = 0.0
                # 매도: 매수호가 중에서 od.price 이상인 가격을 소진
                for level in local_bids:
                    if qty <= 0:
                        break
                    if level["size"] <= 0:
                        continue
                    if level["price"] < px:
                        break  # 더 낮은 가격은 의미 없음
                    take = min(qty, level["size"])
                    qty -= take
                    level["size"] -= take
                    filled_total += take
                    notional += level["price"] * take

                if filled_total > 0:
                    vwap = notional / filled_total
                    self.trades.add_fill("SELL", vwap, filled_total)

                if qty > 0:
                    # 남은 수량은 계속 대기
                    od["qty"] = qty
                    remain_orders.append(od)
            else:
                # 여기서는 SELL만 처리. (BUY 지정가를 추가할 때 반대 로직 작성)
                remain_orders.append(od)

        self._working_orders = remain_orders

    def _fill_against_bids(self, price_limit: float, qty: int, bids):
        """
        price_limit 이하(= 더 좋은 가격 포함)의 매수 호가와 매칭해서 최대 qty까지 체결.
        반환: (filled_qty, vwap) — filled_qty==0이면 vwap는 0
        """
        remain = int(qty)
        filled = 0
        notional = 0.0

        for (p, sz, *_rest) in bids:
            bp = float(p);
            bs = int(sz)
            if bp < price_limit or remain <= 0:
                break
            if bs <= 0:
                continue
            take = min(remain, bs)
            remain -= take
            filled += take
            notional += bp * take

        vwap = (notional / filled) if filled > 0 else 0.0
        return filled, vwap

    def _get_order_qty(self) -> int:
        # 후보 위젯들: QSpinBox류
        for name in ("spin_qty", "spinBox_qty", "qtySpin", "sbQty"):
            w = getattr(self, name, None)
            if w:
                try:
                    return max(1, int(w.value()))
                except Exception:
                    pass
        return 1

    def _get_limit_price(self) -> float | None:
        # DoubleSpinBox → LineEdit 순서로 시도
        for name in ("spin_limit_price", "doubleSpin_limit", "dsbPrice", "spin_price"):
            w = getattr(self, name, None)
            if w:
                try:
                    px = float(w.value())
                    if px > 0:
                        return px
                except Exception:
                    pass
        for name in ("line_limit_price", "lineEdit_price", "lePrice"):
            w = getattr(self, name, None)
            if w:
                try:
                    px = float(w.text())
                    if px > 0:
                        return px
                except Exception:
                    pass
        # 위젯이 없으면 입력창
        px, ok = QtWidgets.QInputDialog.getDouble(self, "지정가 매도", "지정가(Price):", 0.0, 0.0, 1e12, 2)
        if not ok or px <= 0:
            return None
        return float(px)


def closeEvent(self, e):
    try:
        if getattr(self, "ticker", None):
            self.ib.cancelMktDepth(self.ticker.contract)
        if self.ib.isConnected():
            self.ib.disconnect()
    except Exception:
        pass
    e.accept()

class LoginDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setModal(True)
        self.resize(360, 160)

        self.edit_user = QtWidgets.QLineEdit(self)
        self.edit_user.setPlaceholderText("User ID (e.g., demo)")
        self.edit_pass = QtWidgets.QLineEdit(self)
        self.edit_pass.setPlaceholderText("Password (e.g., 1234)")
        self.edit_pass.setEchoMode(
            QtWidgets.QLineEdit.EchoMode.Password if _QT6 else QtWidgets.QLineEdit.Password
        )

        self.lbl_error = QtWidgets.QLabel(self); self.lbl_error.setStyleSheet("color:#e66;")

        btn_login  = QtWidgets.QPushButton("Login", self)
        btn_cancel = QtWidgets.QPushButton("Cancel", self)
        btn_login.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        form = QtWidgets.QFormLayout()
        form.addRow("ID", self.edit_user)
        form.addRow("Password", self.edit_pass)

        v = QtWidgets.QVBoxLayout(self)
        v.addLayout(form)
        v.addWidget(self.lbl_error)
        h = QtWidgets.QHBoxLayout(); h.addStretch(1); h.addWidget(btn_cancel); h.addWidget(btn_login)
        v.addLayout(h)

    def credentials(self):
        return self.edit_user.text().strip(), self.edit_pass.text()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = NasdaqWindow()
    window.show()
    sys.exit(app.exec())
