from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6 import QtGui, QtCore
from PyQt6.QtCore import Qt

from widgets.ui_styles import BLUE_HEADER, apply_header_style, QtAlignCenter, QtAlignRight, QtAlignVCenter


class OrderBookTable:
    """
    UI-only OrderBook (호가창)
    - bids: [(price, qty, level)]
    - asks: [(price, qty, level)]
    - mid: float
    """

    def __init__(self, table: QTableWidget):
        self.table = table
        self._init_ui()

    def _init_ui(self):
        t = self.table
        headers = ["매수잔량", "매수호가", "매도호가", "매도잔량"]
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)

        apply_header_style(t, BLUE_HEADER)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        t.setAlternatingRowColors(True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    # ---------------------------------------------------------
    # v2 핵심 메서드
    # ---------------------------------------------------------
    def set_orderbook(self, bids, asks, mid: float):
        """
        bids: [(price, qty, level)] — 리스트 전체
        asks: [(price, qty, level)]
        mid: 중간호가 (중앙 표시 등)

        UI는 아래 순서로 표시:
            매수잔량 | 매수호가 | 매도호가 | 매도잔량
        """

        t = self.table
        n = max(len(bids), len(asks))
        t.setRowCount(n)

        for i in range(n):
            # 매수호가
            if i < len(bids):
                bid_price, bid_qty, _ = bids[i]
                bid_qty_item = QTableWidgetItem(f"{bid_qty:,.4f}")
                bid_price_item = QTableWidgetItem(f"{bid_price:,.2f}")
            else:
                bid_qty_item = QTableWidgetItem("")
                bid_price_item = QTableWidgetItem("")

            # 매도호가
            if i < len(asks):
                ask_price, ask_qty, _ = asks[i]
                ask_price_item = QTableWidgetItem(f"{ask_price:,.2f}")
                ask_qty_item = QTableWidgetItem(f"{ask_qty:,.4f}")
            else:
                ask_price_item = QTableWidgetItem("")
                ask_qty_item = QTableWidgetItem("")

            # 정렬
            for item in [bid_qty_item, bid_price_item, ask_price_item, ask_qty_item]:
                item.setTextAlignment(QtAlignRight | QtAlignVCenter)

            # 색상 적용
            # 매수호가: 파란색, 매도호가: 빨간색
            bid_price_item.setForeground(QtGui.QBrush(QtGui.QColor("blue")))
            ask_price_item.setForeground(QtGui.QBrush(QtGui.QColor("red")))

            t.setItem(i, 0, bid_qty_item)
            t.setItem(i, 1, bid_price_item)
            t.setItem(i, 2, ask_price_item)
            t.setItem(i, 3, ask_qty_item)

        apply_header_style(self.table, BLUE_HEADER)
