import random
import datetime
from typing import List, Dict

from ui.datasource_yf import YFSource

# ✅ PyQt6 우선, 실패 시 PyQt5 폴백 + 정렬 플래그 별칭 제공
try:
    from PyQt6 import QtWidgets, QtGui, QtCore
    from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
    QtAlignCenter  = QtCore.Qt.AlignmentFlag.AlignCenter
    QtAlignRight   = QtCore.Qt.AlignmentFlag.AlignRight
    QtAlignVCenter = QtCore.Qt.AlignmentFlag.AlignVCenter
except Exception:
    from PyQt5 import QtWidgets, QtGui, QtCore
    from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem
    QtAlignCenter  = QtCore.Qt.AlignCenter
    QtAlignRight   = QtCore.Qt.AlignRight
    QtAlignVCenter = QtCore.Qt.AlignVCenter

from widgets.ui_styles import BLUE_HEADER, apply_header_style


class _BaseTable:
    def __init__(self, table: QTableWidget):
        self.table = table
        self._init_common()

    def _init_common(self):
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
                                   if hasattr(QtWidgets.QAbstractItemView, "EditTrigger")
                                   else QtWidgets.QAbstractItemView.NoEditTriggers)




class StockListTable(_BaseTable):
    def __init__(self, table: QTableWidget, rows: int = 10):
        super().__init__(table)
        self.rows = rows
        self.data: List[List[object]] = []
        self.table.setColumnCount(4)
        self.table.setRowCount(self.rows)
        self.table.setHorizontalHeaderLabels(["종목명", "종목코드", "현재가", "전일대비"])
        apply_header_style(self.table, BLUE_HEADER)

        self.table.setColumnWidth(0, 150)  # 종목명
        self.table.setColumnWidth(1, 120)  # 코드
        self.table.setColumnWidth(2, 100)  # 현재가
        self.table.setColumnWidth(3, 100)  # 전일대비

        self.src = YFSource()
        self.data = []

        self.populate()
        self.timer = QtCore.QTimer(self.table)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(60_000)

    def populate(self):
        rows = []
        for r in self.src.fetch():
            rows.append((r.name, r.code, r.price, r.change_pct))
        self.data = rows[:self.rows]
        self._render()

    def refresh(self):
        self.populate()

    def _render(self):

        t = self.table
        for i, (name, code, price, change) in enumerate(self.data):
            # 종목명
            t.setItem(i, 0, QTableWidgetItem(name))
            # 코드
            t.setItem(i, 1, QTableWidgetItem(code))

            # 가격/등락 표시
            if price is None:
                t.setItem(i, 2, QTableWidgetItem("-"))
                t.setItem(i, 3, QTableWidgetItem("-"))
                continue

            t.setItem(i, 2, QTableWidgetItem(f"{price:,.2f}"))

            arrow = ""
            color = QtGui.QColor("gray")
            if change is not None:
                arrow = "▲" if change > 0 else ("▼" if change < 0 else "—")
                color = QtGui.QColor("red") if change > 0 else (
                    QtGui.QColor("blue") if change < 0 else QtGui.QColor("gray"))
                txt = f"{arrow} {change:.2f}%"
            else:
                txt = "-"

            item_change = QTableWidgetItem(txt)
            item_change.setForeground(QtGui.QBrush(color))
            # item_change.setTextAlignment(Qt.AlignCenter)
            t.setItem(i, 3, item_change)


class TradesTable(_BaseTable):
    def __init__(self, table: QTableWidget, max_rows: int = 30):
        super().__init__(table)
        self.max_rows = max_rows
        self.trades: List[Dict] = []
        self.trade_price: float = 11000.0
        self.table.setColumnCount(3)
        self.table.setRowCount(0)
        self.table.setHorizontalHeaderLabels(["시간", "체결가", "수량"])
        apply_header_style(self.table, BLUE_HEADER)



    def populate(self, initial_count: int = 5):
        self.trades.clear()
        for _ in range(initial_count):
            self._add_trade_internal()
        self._render()

    def add_trade(self):
        self._add_trade_internal()
        self._render()

    def _add_trade_internal(self):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        delta = random.uniform(-10, 10)
        self.trade_price += delta
        qty = random.randint(100, 5000)
        up = delta > 0
        self.trades.insert(0, {"time": now, "price": round(self.trade_price, 2), "qty": qty, "up": up})
        if len(self.trades) > self.max_rows:
            self.trades = self.trades[: self.max_rows]

    # tables.py (TradesTable 내부)
    def add_fill(self, side: str, price: float, qty: int):
        """
        내가 낸 주문 체결을 테이블 상단에 추가.
        side: "BUY" or "SELL"
        """
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")
        up = (side.upper() == "BUY")  # 매수 체결은 빨강, 매도는 파랑
        self.trades.insert(0, {
            "time": now,
            "price": round(float(price), 2),
            "qty": int(qty),
            "up": up,
            "is_fill": True,  # 내가 낸 체결 표시 플래그
            "side": side.upper()
        })
        if len(self.trades) > self.max_rows:
            self.trades = self.trades[: self.max_rows]
        self._render()

    def _render(self):
        t = self.table
        t.setRowCount(len(self.trades))
        for i, tr in enumerate(self.trades):
            time_item = QTableWidgetItem(tr["time"])
            price_item = QTableWidgetItem(f"{tr['price']:,.2f}")
            qty_item = QTableWidgetItem(f"{tr['qty']:,}")

            time_item.setTextAlignment(QtAlignCenter)
            price_item.setTextAlignment(QtAlignRight | QtAlignVCenter)
            qty_item.setTextAlignment(QtAlignRight | QtAlignVCenter)

            color = QtGui.QColor("red") if tr["up"] else QtGui.QColor("blue")
            price_item.setForeground(QtGui.QBrush(color))

            t.setItem(i, 0, time_item)
            t.setItem(i, 1, price_item)
            t.setItem(i, 2, qty_item)

            if tr.get("is_fill"):
                font = price_item.font()
                font.setBold(True)
                time_item.setFont(font)
                price_item.setFont(font)
                qty_item.setFont(font)
                # 연한 노란 배경
                # from PyQt5 import QtGui
                bg = QtGui.QColor(255, 255, 200)
                time_item.setBackground(QtGui.QBrush(bg))
                price_item.setBackground(QtGui.QBrush(bg))
                qty_item.setBackground(QtGui.QBrush(bg))
