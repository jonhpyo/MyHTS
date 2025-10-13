import random
import datetime
from typing import List, Dict

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

from ui_styles import BLUE_HEADER, DARK_HEADER, apply_header_style


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


class OrderBookTable(_BaseTable):
    def __init__(self, table: QTableWidget, row_count: int, base_index: int = 9):
        super().__init__(table)
        self.row_count = row_count
        self.base_index = base_index
        self.data: List[List[float]] = []
        self.table.setRowCount(self.row_count)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["MIT", "매도", "건수", "잔량", "고정", "잔량", "건수", "MIT"])
        apply_header_style(self.table, BLUE_HEADER)
        for i in range(self.row_count):
            self.table.setRowHeight(i, 24)
        self._install_baseline_delegate()

    def populate(self):
        self.data = []
        for _ in range(self.row_count):
            price = round(random.uniform(10000, 12000), 2)
            left_cnt = random.randint(1, 20)
            left_qty = random.randint(100, 2000)
            right_qty = random.randint(100, 2000)
            right_cnt = random.randint(1, 20)
            self.data.append([price, left_cnt, left_qty, right_qty, right_cnt])
        self._render()

    def refresh(self):
        for i, row in enumerate(self.data):
            delta = 0.5 if i == self.base_index else 5
            row[0] += random.uniform(-delta, delta)
            row[1] = max(1, row[1] + random.randint(-2, 2))
            row[2] = max(0, row[2] + random.randint(-100, 100))
            row[3] = max(0, row[3] + random.randint(-100, 100))
            row[4] = max(1, row[4] + random.randint(-2, 2))
        self._render()

    def _render(self):
        t = self.table
        for i, row in enumerate(self.data):
            price, left_cnt, left_qty, right_qty, right_cnt = row

            item_price = QTableWidgetItem(f"{price:,.2f}")
            item_price.setTextAlignment(QtAlignCenter)
            if i == self.base_index:
                item_price.setBackground(QtGui.QColor(255, 255, 100))
                item_price.setForeground(QtGui.QBrush(QtGui.QColor("black")))
            else:
                item_price.setForeground(QtGui.QBrush(QtGui.QColor("black")))
            t.setItem(i, 4, item_price)

            item_cnt_left = QTableWidgetItem(str(left_cnt))
            item_qty_left = QTableWidgetItem(str(left_qty))
            for it in (item_cnt_left, item_qty_left):
                it.setTextAlignment(QtAlignCenter)
                it.setForeground(QtGui.QBrush(QtGui.QColor("lightgreen")))
            t.setItem(i, 2, item_cnt_left)
            t.setItem(i, 3, item_qty_left)

            item_qty_right = QTableWidgetItem(str(right_qty))
            item_cnt_right = QTableWidgetItem(str(right_cnt))
            for it in (item_qty_right, item_cnt_right):
                it.setTextAlignment(QtAlignCenter)
                it.setForeground(QtGui.QBrush(QtGui.QColor("orange")))
            t.setItem(i, 5, item_qty_right)
            t.setItem(i, 6, item_cnt_right)

    def _install_baseline_delegate(self):
        row_index = self.base_index
        table = self.table

        class _BorderDelegate(QtWidgets.QStyledItemDelegate):
            def paint(self, painter, option, index):
                super().paint(painter, option, index)
                if index.row() == row_index:
                    pen = QtGui.QPen(QtGui.QColor(0, 0, 0))
                    pen.setWidth(2)
                    painter.setPen(pen)
                    painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

        table.setItemDelegate(_BorderDelegate(table))


class StockListTable(_BaseTable):
    def __init__(self, table: QTableWidget, rows: int = 10):
        super().__init__(table)
        self.rows = rows
        self.data: List[List[object]] = []
        self.table.setColumnCount(4)
        self.table.setRowCount(self.rows)
        self.table.setHorizontalHeaderLabels(["종목명", "종목코드", "현재가", "전일대비"])
        apply_header_style(self.table, BLUE_HEADER)

    def populate(self):
        names = ["삼성전자", "LG에너지솔루션", "NAVER", "카카오", "현대차", "기아", "POSCO홀딩스", "셀트리온", "SK하이닉스", "한화솔루션"]
        self.data.clear()
        for name in names[: self.rows]:
            code = str(random.randint(100000, 999999))
            price = random.randint(30000, 200000)
            change = round(random.uniform(-3, 3), 2)
            self.data.append([name, code, price, change])
        self._render()

    def refresh(self):
        for s in self.data:
            s[3] += random.uniform(-0.2, 0.2)
            s[2] *= (1 + s[3] / 100)
        self._render()

    def _render(self):
        t = self.table
        for i, (name, code, price, change) in enumerate(self.data):
            t.setItem(i, 0, QTableWidgetItem(name))
            t.setItem(i, 1, QTableWidgetItem(code))
            t.setItem(i, 2, QTableWidgetItem(f"{price:,.0f}"))

            arrow = "▲" if change > 0 else ("▼" if change < 0 else "―")
            item_change = QTableWidgetItem(f"{arrow} {abs(change):.2f}%")
            color = QtGui.QColor("red") if change > 0 else (QtGui.QColor("blue") if change < 0 else QtGui.QColor("gray"))
            item_change.setForeground(QtGui.QBrush(color))
            item_change.setTextAlignment(QtAlignCenter)
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
