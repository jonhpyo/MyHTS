"""
charts.py — Reusable candle + volume chart widget for PyQt5 (pyqtgraph)

• Drop-in widget: CandleChartWidget(max_visible=120)
• Works with your own Candle dataclass OR raw API rows via update_from_api_rows(...)
• Built-in resampling for timeframes: 1D / 1W / 1M / 1Y (pandas resample rules)
• Dark theme by default
• Optional: run this file directly to see a synthetic demo

Dependencies
------------
    pip install PyQt5 pyqtgraph pandas numpy

API adapters
------------
- candles_from_polygon(rows): Polygon aggregates -> List[Candle]
  rows keys: t(ms), o,h,l,c,v
- candles_from_alpaca_bars(bars): Alpaca v2 bars -> List[Candle]
  bars keys: t(ISO8601), o,h,l,c,v

"""
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets, QtGui

# ---- Appearance -----------------------------------------------------------
pg.setConfigOptions(antialias=True)
pg.setConfigOption("foreground", "w")
pg.setConfigOption("background", (25, 28, 35))


# ---- Data model -----------------------------------------------------------
@dataclass
class Candle:
    t: float  # epoch seconds (UTC)
    o: float
    h: float
    l: float
    c: float
    v: float


# ---- Adapters (API rows -> Candle list) ----------------------------------
def candles_from_polygon(rows: Optional[List[dict]]) -> List[Candle]:
    """Polygon aggregates rows (t=ms, o,h,l,c,v) -> List[Candle]."""
    if not rows:
        return []
    out: List[Candle] = []
    for r in rows:
        try:
            t = float(r["t"]) / 1000.0  # ms -> sec
            out.append(Candle(
                t=t,
                o=float(r["o"]),
                h=float(r["h"]),
                l=float(r["l"]),
                c=float(r["c"]),
                v=float(r.get("v", 0.0)),
            ))
        except Exception:
            continue
    return out


def candles_from_alpaca_bars(bars: Optional[List[dict]]) -> List[Candle]:
    """Alpaca v2 bars (t=ISO8601, o,h,l,c,v) -> List[Candle]."""
    if not bars:
        return []
    out: List[Candle] = []
    for b in bars:
        try:
            ts = datetime.fromisoformat(b["t"].replace("Z", "+00:00"))
            t = ts.replace(tzinfo=timezone.utc).timestamp()
            out.append(Candle(
                t=t,
                o=float(b["o"]),
                h=float(b["h"]),
                l=float(b["l"]),
                c=float(b["c"]),
                v=float(b.get("v", 0.0)),
            ))
        except Exception:
            continue
    return out


# ---- Main widget ----------------------------------------------------------
class CandleChartWidget(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None, max_visible: int = 120):
        super().__init__(parent)
        self.max_visible = max_visible
        self.timeframe = "1H"
        # self.valid_tfs = {"1D": "D", "1W": "W", "1M": "ME", "1Y": "YE"}
        # self.valid_tfs = {"1H": "H", "1D": "D", "1W": "W", "1M": "ME", "1Y": "YE"}
        self.valid_tfs = {"1H": "h", "1D": "d", "1W": "w", "1M": "ME", "1Y": "YE"}

        # Price plot --------------------------------------------------------
        self.price_plot = self.addPlot(row=0, col=0)
        self.price_plot.showGrid(x=True, y=True, alpha=0.3)
        self.price_plot.setLabel("left", "Price")
        self.price_plot.setAxisItems({"bottom": pg.DateAxisItem(orientation="bottom")})

        # Volume plot -------------------------------------------------------
        self.nextRow()
        self.vol_plot = self.addPlot(row=1, col=0)
        self.vol_plot.showGrid(x=True, y=True, alpha=0.3)
        self.vol_plot.setLabel("left", "Volume")
        self.vol_plot.setXLink(self.price_plot)

        # Dataframes --------------------------------------------------------
        self.base_df = pd.DataFrame(columns=["t", "o", "h", "l", "c", "v"]).astype(float)
        self.view_df = self.base_df.copy()

        # Items -------------------------------------------------------------
        self.candle_item = _CandlestickItem()
        self.price_plot.addItem(self.candle_item)
        self.vol_up = pg.BarGraphItem(x=[], height=[], width=0.8, brush=(200, 80, 80))
        self.vol_down = pg.BarGraphItem(x=[], height=[], width=0.8, brush=(80, 120, 200))
        self.vol_plot.addItem(self.vol_up)
        self.vol_plot.addItem(self.vol_down)

        # Crosshair ---------------------------------------------------------
        self._vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen((150,150,150), width=1))
        self._hline = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen((150,150,150), width=1))
        self.price_plot.addItem(self._vline, ignoreBounds=True)
        self.price_plot.addItem(self._hline, ignoreBounds=True)
        self.proxy = pg.SignalProxy(self.price_plot.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_move)

    # --- Public API -------------------------------------------------------
    def set_timeframe(self, tf: str):
        if tf not in self.valid_tfs:
            return
        self.timeframe = tf
        self._apply_timeframe()
        self._refresh_graph()

    def add_candles(self, candles: List[Candle]):
        """Append multiple Candle objects."""
        if not candles:
            return
        rows = [[c.t, c.o, c.h, c.l, c.c, c.v] for c in candles]
        new = pd.DataFrame(rows, columns=self.base_df.columns).astype(float)
        self.base_df = pd.concat([self.base_df, new], ignore_index=True)
        self._trim_base(); self._apply_timeframe(); self._refresh_graph()

    def add_candle(self, candle: Candle):
        new = pd.DataFrame([[candle.t, candle.o, candle.h, candle.l, candle.c, candle.v]],
                           columns=self.base_df.columns).astype(float)
        self.base_df = pd.concat([self.base_df, new], ignore_index=True)
        self._trim_base(); self._apply_timeframe(); self._refresh_graph()

    def update_last_candle(self, candle: Candle):
        if self.base_df.empty:
            self.add_candle(candle)
            return
        self.base_df.iloc[-1] = [candle.t, candle.o, candle.h, candle.l, candle.c, candle.v]
        self._apply_timeframe(); self._refresh_graph()

    def update_from_api_rows(self, rows: Optional[List[dict]], source: str = "polygon", replace: bool = False):
        """
        Feed raw API rows directly.
        - source="polygon"  : rows of {t(ms), o,h,l,c,v}
        - source="alpaca"   : rows of {t(ISO8601), o,h,l,c,v}
        - replace=True      : clear and redraw (for initial load)
        """
        if source == "alpaca":
            candles = candles_from_alpaca_bars(rows)
        else:
            candles = candles_from_polygon(rows)

        if not candles:
            return

        if replace:
            self.base_df = pd.DataFrame([[c.t, c.o, c.h, c.l, c.c, c.v] for c in candles],
                                        columns=self.base_df.columns).astype(float)
            self._trim_base(); self._apply_timeframe(); self._refresh_graph()
            return

        # streaming append/update
        for c in candles:
            if not self.base_df.empty and abs(self.base_df.iloc[-1]["t"] - c.t) < 1e-6:
                self.update_last_candle(c)
            else:
                self.add_candle(c)

    # --- Internals --------------------------------------------------------
    def _trim_base(self):
        if len(self.base_df) > 5000:
            self.base_df = self.base_df.iloc[-5000:].reset_index(drop=True)

    def _apply_timeframe(self):
        if self.base_df is None or self.base_df.empty:
            self.view_df = self.base_df.copy()
            return

        df = self.base_df.copy()
        df["dt"] = pd.to_datetime(df["t"], unit="s")
        df = df.set_index("dt")

        rule = self.valid_tfs[self.timeframe]
        res = df.resample(rule).agg({
            "o": "first", "h": "max", "l": "min",
            "c": "last", "v": "sum", "t": "last"
        }).dropna(subset=["o", "c"])

        if len(res) > self.max_visible:
            res = res.iloc[-self.max_visible:]

        res = res.reset_index()
        res["t"] = (res["dt"].astype("int64") // 10 ** 9).astype(float)
        self.view_df = res[["t", "o", "h", "l", "c", "v"]]

    def _refresh_graph(self):
        if self.view_df is None or self.view_df.empty:
            return
        x = self.view_df["t"].to_numpy()
        o = self.view_df["o"].to_numpy()
        h = self.view_df["h"].to_numpy()
        l = self.view_df["l"].to_numpy()
        c = self.view_df["c"].to_numpy()
        v = self.view_df["v"].to_numpy()

        self.candle_item.set_data(x, o, h, l, c)

        up = c >= o
        self.vol_up.setOpts(x=x[up], height=v[up], width=self._bar_width(x))
        self.vol_down.setOpts(x=x[~up], height=v[~up], width=self._bar_width(x))

        # self.price_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        # self.vol_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.price_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)
        self.vol_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)

        self.price_plot.setXRange(float(x.max()) - self._visible_span(x), float(x.max()), padding=0)
        self.vol_plot.setXRange(*self.price_plot.viewRange()[0], padding=0)

    def _bar_width(self, x: np.ndarray) -> float:
        if len(x) < 2:
            return 60.0
        d = np.diff(np.sort(x))
        return float(np.median(d)) * 0.8

    def _visible_span(self, x: np.ndarray) -> float:
        if len(x) < 2:
            return 3600.0
        d = np.diff(np.sort(x))
        step = np.median(d)
        return float(step * (len(x) - 1))

    def _on_mouse_move(self, evt):
        pos: QtCore.QPointF = evt[0]
        if self.price_plot.sceneBoundingRect().contains(pos):
            vb: pg.ViewBox = self.price_plot.getViewBox()
            mousePoint = vb.mapSceneToView(pos)
            self._vline.setPos(mousePoint.x())
            self._hline.setPos(mousePoint.y())


# ---- Custom graphics: cached candlesticks -------------------------------
class _CandlestickItem(pg.GraphicsObject):
    def __init__(self):
        super().__init__()
        self.x = np.array([])
        self.o = np.array([])
        self.h = np.array([])
        self.l = np.array([])
        self.c = np.array([])
        self.picture: Optional[QtGui.QPicture] = None

    def set_data(self, x, o, h, l, c):
        self.x, self.o, self.h, self.l, self.c = map(np.asarray, (x, o, h, l, c))
        self._generate_picture()
        self.informViewBoundsChanged()

    def _generate_picture(self):
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)

        up_pen = pg.mkPen((220, 90, 90))
        up_brush = pg.mkBrush((220, 90, 90))
        dn_pen = pg.mkPen((90, 120, 220))
        dn_brush = pg.mkBrush((90, 120, 220))

        w = self._body_width()

        for xx, oo, hh, ll, cc in zip(self.x, self.o, self.h, self.l, self.c):
            up = cc >= oo
            pen = up_pen if up else dn_pen
            brush = up_brush if up else dn_brush
            p.setPen(pen)
            p.drawLine(QtCore.QPointF(xx, ll), QtCore.QPointF(xx, hh))
            top, bot = max(oo, cc), min(oo, cc)
            rect = QtCore.QRectF(xx - w/2, bot, w, max(0.0001, top - bot))
            p.fillRect(rect, brush)
            p.drawRect(rect)
        p.end()

    def _body_width(self) -> float:
        if len(self.x) < 2:
            return 30.0
        d = np.diff(np.sort(self.x))
        return float(np.median(d)) * 0.6

    def paint(self, p, *args):
        if self.picture is not None:
            p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        if len(self.x) == 0:
            return pg.QtCore.QRectF()
        return pg.QtCore.QRectF(
            float(np.min(self.x)),
            float(np.min(self.l)),
            float(np.max(self.x) - np.min(self.x)),
            float(np.max(self.h) - np.min(self.l)),
        )


# ---- Standalone demo -----------------------------------------------------
if __name__ == "__main__":
    import random

    app = QtWidgets.QApplication([])
    w = QtWidgets.QMainWindow(); w.resize(960, 640); w.setWindowTitle("charts.py demo")
    chart = CandleChartWidget(max_visible=180)
    chart.set_timeframe("1D")  # try: "1W", "1M"
    w.setCentralWidget(chart)
    w.show()

    # Seed with synthetic intraday candles (epoch seconds)
    now = int(datetime.utcnow().timestamp())
    base = 18300.0
    rows = []
    for i in range(240):
        t = now - (240 - i) * 60
        o = base
        c = base + (random.random() - 0.5) * 2.0
        h = max(o, c) + random.random() * 1.0
        l = min(o, c) - random.random() * 1.0
        v = 100 + int(random.random() * 50)
        rows.append({"t": t * 1000, "o": o, "h": h, "l": l, "c": c, "v": v})
        base = c

    # Use the polygon adapter (ms -> sec) for the demo rows
    chart.update_from_api_rows(rows, source="polygon", replace=True)

    # Live tick: append one candle per second
    def tick():
        global now, base
        now += 60
        o = base
        c = base + (random.random() - 0.5) * 2.0
        h = max(o, c) + random.random() * 1.0
        l = min(o, c) - random.random() * 1.0
        v = 100 + int(random.random() * 50)
        latest = {"t": now * 1000, "o": o, "h": h, "l": l, "c": c, "v": v}
        chart.update_from_api_rows([latest], source="polygon", replace=False)
        base = c

    timer = QtCore.QTimer(); timer.timeout.connect(tick); timer.start(1000)
    app.exec_()
