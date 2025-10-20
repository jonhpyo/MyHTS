# app.py
from __future__ import annotations

import os
import random
import sys
import time
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

from UI.databento_bridge import DatabentoBridge
from UI.polygon_ws_bridge import PolygonWSBridge
from ib_depth_bridge import IBDepthBridge
from orderbook_table import OrderBookTable


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
from charts import CandleChartWidget, Candle



# from adapters.kiwoom import KiwoomSource as DataSource

USE = os.getenv("DATA_SOURCE", "ALPACA")
if USE.upper() == "ALPACA":
    from adapters.alpaca import AlpacaSource as DataSource
# elif USE.upper() == "NASDAQ":
#     from adapters.nq_polygon_pygt import
else:
    from adapters.kis import KISSource as DataSource

class NasdaqWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("nasdaq_extended.ui", self)
        self.setWindowTitle("NASDAQ EXTENDED (모의 API)")

        self.orderbook = OrderBookTable(self.table_hoga, row_count=21, base_index=10)
        self.stocklist = StockListTable(self.table_stocklist, rows=10)
        self.trades = TradesTable(self.table_trades, max_rows=30)

        # self.orderbook.populate()
        # self.stocklist.populate()
        # self.trades.populate(initial_count=5)

        self._pending = None

        self.button_chart.clicked.connect(self.open_chart_window)

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
        self.timer.timeout.connect(self._flush)
        self.timer.start(150)


    # def _flush(self):
    #     pending = getattr(self, "_pending", None)
    #     if not pending:
    #         return
    #     bids, asks, mid = pending
    #     self._pending = None
    #     self.orderbook.set_orderbook(bids=bids, asks=asks, mid_price=mid)

    def _flush(self):
        if not self._pending:
            return
        bids, asks, mid = self._pending
        self._pending = None
        self.orderbook.set_orderbook(bids=bids, asks=asks, mid_price=mid)



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

def closeEvent(self, e):
    try:
        if getattr(self, "ticker", None):
            self.ib.cancelMktDepth(self.ticker.contract)
        if self.ib.isConnected():
            self.ib.disconnect()
    except Exception:
        pass
    e.accept()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = NasdaqWindow()
    window.show()
    sys.exit(app.exec())
