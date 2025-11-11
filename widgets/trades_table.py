# orderbook_table.py
from __future__ import annotations
import random
from typing import List, Optional, Sequence, Tuple
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
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
        self.table.setColumnCount(7)
        self.table.setRowCount(0)
        self.table.setHorizontalHeaderLabels(["계좌번호", "종목", "매도/매수", "체결가", "체결수량", "체결시간", "비고"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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

    def render_from_db(self, trade_rows):
        """
        DB에서 읽은 체결내역 리스트를 테이블에 표시
        컬럼: 계좌번호 | 종목 | 매도/매수 | 체결가 | 체결수량 | 체결시간 | 비고
        """
        t = self.table
        t.clearContents()

        headers = ["계좌번호", "종목", "매도/매수", "체결가", "체결수량", "체결시간", "비고"]
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)

        print("[TradesTable] render_from_db called. rows =", len(trade_rows))

        if not trade_rows:
            t.setRowCount(0)
            return

        # 디버그: 첫 행 구조 찍어보기 (여기서 안 죽게 최대한 안전하게)
        first = trade_rows[0]
        try:
            if hasattr(first, "keys"):
                print("[TradesTable] first row type:", type(first), "keys:", list(first.keys()))
            else:
                print("[TradesTable] first row type:", type(first), "value:", first)
        except Exception as dbg_err:
            print("[TradesTable] debug error:", dbg_err)

        try:
            t.setRowCount(len(trade_rows))

            for i, row in enumerate(trade_rows):
                try:
                    # 1) DictRow / dict 케이스
                    if hasattr(row, "keys"):
                        acc_no = row.get("account_no", "")
                        symbol = row.get("symbol", "")
                        side = str(row.get("side", "")).upper()
                        price = float(row.get("price", 0.0))
                        qty = float(row.get("quantity", 0.0))
                        trade_time = row.get("trade_time", None)
                        remark = row.get("remark", "")
                    # 2) tuple/list 케이스 (컬럼 순서에 맞게 인덱스 사용)
                    else:
                        # 예: SELECT account_no, symbol, side, price, quantity, trade_time, remark
                        acc_no, symbol, side, price, qty, trade_time, remark = row
                        side = str(side).upper()
                        price = float(price)
                        qty = float(qty)

                    # 시간 문자열 변환
                    if hasattr(trade_time, "strftime"):
                        trade_time_str = trade_time.strftime("%H:%M:%S")
                    else:
                        trade_time_str = str(trade_time or "")

                    # 색상 (BUY=빨강, SELL=파랑)
                    color = QtGui.QColor("red") if side == "BUY" else QtGui.QColor("blue")

                    # 셀 아이템 생성
                    items = [
                        QTableWidgetItem(acc_no),
                        QTableWidgetItem(symbol),
                        QTableWidgetItem(side),
                        QTableWidgetItem(f"{price:,.2f}"),
                        QTableWidgetItem(f"{qty:,.4f}"),
                        QTableWidgetItem(trade_time_str),
                        QTableWidgetItem(remark),
                    ]

                    # 정렬 / 색상 적용
                    for j, item in enumerate(items):
                        if j in (0, 1, 2, 5, 6):  # 계좌, 종목, 매도/매수, 시간, 비고
                            align = QtAlignCenter
                        else:  # 체결가, 체결수량
                            align = QtAlignRight | QtAlignVCenter
                        item.setTextAlignment(align)
                        if j in (2, 3, 4):  # 매도/매수, 체결가, 체결수량에만 색 적용
                            item.setForeground(QtGui.QBrush(color))
                        t.setItem(i, j, item)

                except Exception as row_err:
                    print(f"[TradesTable] Row {i} 렌더링 중 오류:", row_err)
                    continue

            t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            apply_header_style(self.table, BLUE_HEADER)

        except Exception as e:
            print("[TradesTable] render_from_db 전체 오류:", e)
            import traceback
            traceback.print_exc()



