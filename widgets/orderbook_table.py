# orderbook_table.py
from __future__ import annotations
import random
from typing import List, Optional, Sequence, Tuple
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
from PyQt6.QtCore import Qt
from widgets.ui_styles import BLUE_HEADER, apply_header_style


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

class OrderBookTable(_BaseTable):
    """
    8열 호가 테이블
    [0]=MIT(L), [1]=매도(가격), [2]=건수(L), [3]=잔량(L),
    [4]=고정(중앙가격), [5]=잔량(R), [6]=건수(R), [7]=MIT(R)

    - base_index 행에 굵은 하단 구분선
    - set_orderbook(bids, asks, mid_price)로 실데이터 주입
      bids: 내림차순 [(price, qty, cnt), ...]
      asks: 오름차순 [(price, qty, cnt), ...]
    """
    def __init__(self, table: QTableWidget, row_count: int, base_index: int = 9):
        super().__init__(table)
        self.row_count = row_count
        self.base_index = base_index
        # 각 행: [price, left_cnt, left_qty, right_qty, right_cnt]
        self.data: List[List[float | int | None]] = []

        self.table.setRowCount(self.row_count)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["MIT", "매도", "건수", "잔량", "고정", "잔량", "건수", "MIT"])
        apply_header_style(self.table, BLUE_HEADER)

        widths = [70, 80, 80, 80, 90, 80, 80, 80]

        for c, w in enumerate(widths):
            self.table.setColumnWidth(c, w)
        self.table.verticalHeader().setVisible(False)
        for i in range(self.row_count):
            self.table.setRowHeight(i, 24)

        self._install_baseline_delegate()
        self._init_empty_rows()



    def _init_empty_rows(self):
        self.data = [[None, 0, 0, 0, 0] for _ in range(self.row_count)]
        self._render()

    # ------ 데모용 더미 ------
    def populate(self):
        self.data = []
        base_price = 17000.0
        # for i in range(self.row_count):
        #     delta = 1.0 if i == self.base_index else 10.0
        #     price = round(base_price + (i - self.base_index) * delta, 2)
        #     left_cnt  = random.randint(1, 20)
        #     left_qty  = random.randint(1, 50)
        #     right_qty = random.randint(1, 50)
        #     right_cnt = random.randint(1, 20)
        #     self.data.append([price, left_cnt, left_qty, right_qty, right_cnt])
        self._render()

    def refresh(self):
        if not self.data:
            # return self.populate()
            return
        for i, row in enumerate(self.data):
            price, left_cnt, left_qty, right_qty, right_cnt = row
            pdelta = 1.0 if i == self.base_index else 10.0
            row[0] = round((price or 0) + random.uniform(-pdelta, pdelta), 2)
            row[1] = max(1, int(left_cnt) + random.randint(-2, 2))
            row[2] = max(0, int(left_qty) + random.randint(-5, 5))
            row[3] = max(0, int(right_qty) + random.randint(-5, 5))
            row[4] = max(1, int(right_cnt) + random.randint(-2, 2))
        self._render()

    # ------ 실데이터 주입 ------
    def set_orderbook(
        self,
        bids: Sequence[Tuple[float, int, int]],
        asks: Sequence[Tuple[float, int, int]],
        mid_price: Optional[float] = None,
    ):
        self._init_empty_rows()  # 초기화 후 채우기

        if mid_price is None:
            pxs = []
            if bids: pxs.append(bids[0][0])
            if asks: pxs.append(asks[0][0])
            if pxs:
                mid_price = sum(pxs) / len(pxs)
        if mid_price is None:
            mid_price = 0.0

        self.data[self.base_index][0] = float(mid_price)

        # asks는 기준행 위로
        ai = self.base_index - 1
        for price, qty, cnt in asks:
            if ai < 0: break
            self.data[ai][0] = float(price)
            self.data[ai][3] = int(qty)   # right_qty
            self.data[ai][4] = int(cnt)   # right_cnt
            ai -= 1

        # bids는 기준행 아래로
        bi = self.base_index + 1
        for price, qty, cnt in bids:
            if bi >= self.row_count: break
            self.data[bi][0] = float(price)
            self.data[bi][2] = int(qty)   # left_qty
            self.data[bi][1] = int(cnt)   # left_cnt
            bi += 1

        self._render()

    def _flush_depth_to_ui(self):
        """버퍼→OrderBookTable 반영 + 최근 호가 저장"""
        if not self._pending:
            return
        bids, asks, mid = self._pending
        self._pending = None
        # 최신 호가 저장
        self._last_depth = (bids, asks, mid)
        # 화면 반영
        self.orderbook.set_orderbook(bids=bids, asks=asks, mid_price=mid)

    def _render(self):
        t = self.table
        ALIGN_C = Qt.AlignmentFlag.AlignCenter

        for i, row in enumerate(self.data):
            price, left_cnt, left_qty, right_qty, right_cnt = row

            # 중앙 가격
            item_price = QTableWidgetItem("" if price is None else f"{price:,.2f}")
            item_price.setTextAlignment(ALIGN_C)
            if i == self.base_index:
                item_price.setBackground(QtGui.QColor(255, 255, 120))
                item_price.setForeground(QtGui.QBrush(QtGui.QColor("black")))
            t.setItem(i, 4, item_price)

            # 좌측(매수)
            it_cnt_l = QTableWidgetItem("" if not left_cnt else str(left_cnt))
            it_qty_l = QTableWidgetItem("" if not left_qty else str(left_qty))
            for it in (it_cnt_l, it_qty_l):
                it.setTextAlignment(ALIGN_C)
                it.setForeground(QtGui.QBrush(QtGui.QColor(0, 140, 0)))  # 녹색톤
            t.setItem(i, 2, it_cnt_l)
            t.setItem(i, 3, it_qty_l)

            # 우측(매도)
            it_qty_r = QTableWidgetItem("" if not right_qty else str(right_qty))
            it_cnt_r = QTableWidgetItem("" if not right_cnt else str(right_cnt))
            for it in (it_qty_r, it_cnt_r):
                it.setTextAlignment(ALIGN_C)
                it.setForeground(QtGui.QBrush(QtGui.QColor(200, 120, 0)))  # 주황톤
            t.setItem(i, 5, it_qty_r)
            t.setItem(i, 6, it_cnt_r)

            # 가격 라벨(매도 가격 칸)
            it_px_right = QTableWidgetItem("" if price is None else f"{price:,.2f}")
            it_px_right.setTextAlignment(ALIGN_C)
            t.setItem(i, 1, it_px_right)

            # 양끝 MIT는 비워두거나 아이콘 사용 가능
            t.setItem(i, 0, QTableWidgetItem(""))
            t.setItem(i, 7, QTableWidgetItem(""))

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
