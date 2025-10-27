# orderbook_table.py
from __future__ import annotations
import random
from typing import List, Optional, Sequence, Tuple
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
from PyQt6.QtCore import Qt

from widgets.ui_styles import QtAlignCenter, QtAlignRight, QtAlignVCenter
from widgets.ui_styles import BLUE_HEADER, DARK_HEADER, apply_header_style

import random
import datetime
from typing import List, Dict

from ui.datasource_yf import YFSource
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