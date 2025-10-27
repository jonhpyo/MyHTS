# orderbook_table.py
from __future__ import annotations
import random
from typing import List, Optional, Sequence, Tuple
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
from PyQt6.QtCore import Qt

from .ui_styles import QtAlignCenter, QtAlignRight, QtAlignVCenter
from .ui_styles import BLUE_HEADER, DARK_HEADER, apply_header_style

import random
import datetime
from typing import List, Dict

# 간단 헤더 스타일 (자유 수정)
# BLUE_HEADER = {"bg": QtGui.QColor(235, 242, 255), "fg": QtGui.QColor(30, 30, 30)}

# def apply_header_style(table: QtWidgets.QTableWidget, style=BLUE_HEADER):
#     header = table.horizontalHeader()
#     header.setStretchLastSection(False)
#     header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
#     pal = table.palette()
#     table.setPalette(pal)
#     table.setAlternatingRowColors(True)
#     # 색은 필요 시 QSS로:
#     table.setStyleSheet(
#         "QHeaderView::section {"
#         f"background-color: rgb({style['bg'].red()}, {style['bg'].green()}, {style['bg'].blue()});"
#         f"color: rgb({style['fg'].red()}, {style['fg'].green()}, {style['fg'].blue()});"
#         "font-weight: 600;}"
#     )

class _BaseTable:
    def __init__(self, table: QTableWidget):
        self.table = table

class TradesTable(_BaseTable):
    def __init__(self, table: QTableWidget, max_rows: int = 30):
        super().__init__(table)
        self.max_rows = max_rows
        self.trades: List[Dict] = []
        self.trade_price: float = 11000.0
        self.table.setColumnCount(5)
        self.table.setRowCount(0)
        self.table.setHorizontalHeaderLabels(["연번", "시간", "체결가", "수량", "비고"])
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
