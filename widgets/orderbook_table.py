from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6 import QtGui, QtCore, QtWidgets
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
        self.rows = 10

    def _init_ui(self):
        t = self.table
        headers = ["매도잔량", "건수", "고정", "건수", "매수잔량"]
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)

        apply_header_style(t, BLUE_HEADER)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        t.setAlternatingRowColors(True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def render_from_api(self, data):
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        fixed = data.get("fixed_price", None)

        rows = max(len(bids), len(asks))
        self.table.setRowCount(rows)

        for i in range(rows):
            # 매도 (asks)
            if i < len(asks):
                ask_qty = asks[i]["qty"]
                ask_cnt = asks[i]["cnt"]
            else:
                ask_qty = ""
                ask_cnt = ""

            # 매수 (bids)
            if i < len(bids):
                bid_qty = bids[i]["qty"]
                bid_cnt = bids[i]["cnt"]
            else:
                bid_qty = ""
                bid_cnt = ""

            # 고정 가격(BINANCE)
            fixed_str = f"{fixed:.2f}" if fixed else "----"

            # 5개 컬럼 세팅
            values = [
                ask_qty, ask_cnt,
                fixed_str,
                bid_cnt, bid_qty
            ]

            for c, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                item.setTextAlignment(QtAlignCenter)
                self.table.setItem(i, c, item)

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

    def render_combined(self, asks, mid, bids):
        t = self.table

        # 먼저 전체 지우기
        for r in range(self.rows):
            for c in range(t.columnCount()):
                t.setItem(r, c, QtWidgets.QTableWidgetItem(""))

        # ask → 위쪽부터 채움
        for i, a in enumerate(asks[:self.rows]):
            t.setItem(i, 0, QtWidgets.QTableWidgetItem(f"{a['qty']:.4f}"))
            t.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{a['price']:.2f}"))
            t.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{a['cnt']}"))

        # mid price → 가운데 고정
        mid_row = self.rows // 2
        if mid is not None:
            t.setItem(mid_row, 3, QtWidgets.QTableWidgetItem(f"{mid:.2f}"))

        # bid → 아래쪽
        for i, b in enumerate(bids[:self.rows]):
            row = self.rows - 1 - i
            t.setItem(row, 6, QtWidgets.QTableWidgetItem(f"{b['qty']:.4f}"))
            t.setItem(row, 5, QtWidgets.QTableWidgetItem(f"{b['price']:.2f}"))
            t.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{b['cnt']}"))