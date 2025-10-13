# app.py
import sys, time, random, os
import webbrowser

import webview
from PyQt6.QtCore import QTimer
# from PyQt5 import QtWidgets, uic
# from PyQt5.QtCore import QTimer, QUrl
# from PySide6.QtWebEngineWidgets import QWebEngineView
from dotenv import load_dotenv
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
from tables import OrderBookTable, StockListTable, TradesTable
from charts import CandleChartWidget, Candle



# from adapters.kiwoom import KiwoomSource as DataSource

USE = os.getenv("DATA_SOURCE", "ALPACA")
if USE.upper() == "ALPACA":
    from adapters.alpaca import AlpacaSource as DataSource
# elif USE.upper() == "NASDAQ":
#     from adapters.nq_polygon_pygt import
else:
    from adapters.kis import KISSource as DataSource

class CandleWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Candle Chart (Mock API)")
        self.resize(1100, 650)

        self.chart = CandleChartWidget(max_visible=200)
        self.setCentralWidget(self.chart)

        self.src = DataSource()
        self.symbol = os.getenv("SYMBOL", "QQQ")
        print(self.symbol)

        try:
            bars = self.src.get_recent_bars(self.symbol, timeframe="1m", limit=300)
        except Exception as e:
            print("초기 캔들 로드 실패:", e)
            bars = []
        if bars:
            self.chart.add_candles([Candle(b.ts, b.o, b.h, b.l, b.c, b.v) for b in bars])
            last_c = bars[-1].c
        else:
            now = int(time.time())
            last_c = 11000.0
            dummy = []
            for i in range(300):
                t = now - (299 - i) * 60
                o = last_c
                h = o + random.uniform(0, 30)
                l = o - random.uniform(0, 30)
                c = random.uniform(l, h)
                v = random.randint(200, 5000)
                dummy.append(Candle(t, o, h, l, c, v))
                last_c = c
            self.chart.add_candles(dummy)

        self.chart.set_timeframe("1H")

        self._accum = {"o": None, "h": None, "l": None, "v": 0, "start_ts": (int(time.time())//60+1)*60}
        self._last_price = last_c

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

        tb = QtWidgets.QToolBar("Timeframe", self)
        self.addToolBar(tb)
        lbl = QtWidgets.QLabel("단위: ")
        tb.addWidget(lbl)
        self.cmb_tf = QtWidgets.QComboBox()
        self.cmb_tf.addItems(["분", "일", "주", "월", "년"])
        tb.addWidget(self.cmb_tf)
        self._tf_map = {"분": "1H", "일": "1D", "주": "1W", "월": "1M", "년": "1Y"}
        self.cmb_tf.currentTextChanged.connect(self._on_tf_changed)
        self.cmb_tf.setCurrentText("분")

    def _on_tf_changed(self, text: str):
        tf = self._tf_map.get(text, "1H")
        self.chart.set_timeframe(tf)

    def _tick(self):
        try:
            ts, price, qty = self.src.get_last_trade(self.symbol)
        except Exception:
            ts = int(time.time())
            price = self._last_price + random.uniform(-10, 10)
            qty = random.randint(10, 200)

        self._last_price = price

        acc = self._accum
        if acc["o"] is None:
            acc.update(o=price, h=price, l=price, v=0)
        acc["h"] = max(acc["h"], price)
        acc["l"] = min(acc["l"], price)
        acc["v"] += qty

        if ts < acc["start_ts"]:
            self.chart.update_last_candle(Candle(acc["start_ts"]-60, acc["o"], acc["h"], acc["l"], price, acc["v"]))
        else:
            self.chart.add_candle(Candle(acc["start_ts"]-60, acc["o"], acc["h"], acc["l"], price, acc["v"]))
            acc["start_ts"] += 60
            acc.update(o=price, h=price, l=price, v=0)

class NasdaqWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("nasdaq_extended.ui", self)
        self.setWindowTitle("NASDAQ EXTENDED (모의 API)")

        self.orderbook = OrderBookTable(self.table_hoga, row_count=30, base_index=9)
        self.stocklist = StockListTable(self.table_stocklist, rows=10)
        self.trades = TradesTable(self.table_trades, max_rows=30)

        self.orderbook.populate()
        self.stocklist.populate()
        self.trades.populate(initial_count=5)

        self.button_chart.clicked.connect(self.open_chart_window)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self._chart_windows = []

    def _tick(self):
        self.orderbook.refresh()
        self.stocklist.refresh()
        self.trades.add_trade()

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




if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = NasdaqWindow()
    window.show()
    sys.exit(app.exec())
