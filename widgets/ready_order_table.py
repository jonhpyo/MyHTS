# widgets/ready_order_table.py
try:
    from PyQt6 import QtWidgets, QtGui
    from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
    _QT6 = True
except Exception:
    from PyQt5 import QtWidgets, QtGui
    from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem
    _QT6 = False

from .ui_styles import BLUE_HEADER, apply_header_style, QtAlignCenter, QtAlignRight, QtAlignVCenter
from models.working_order import WorkingOrder
from models.order import Side


class ReadyOrdersTable:
    """미체결 주문(WorkingOrder) 리스트를 표시하는 테이블"""

    def __init__(self, table: QTableWidget):
        self.table = table
        self._init_ui()

    def _init_ui(self):
        t = self.table
        headers = ["주문ID", "종목", "매도/매수", "가격", "총수량", "잔량", "주문시간"]
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        apply_header_style(t, BLUE_HEADER)
        t.verticalHeader().setVisible(False)

        # ✅ PyQt6 / PyQt5 호환 분기
        if hasattr(QtWidgets.QAbstractItemView, "EditTrigger"):
            t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        else:
            t.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            t.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

    def render(self, working_orders: list[WorkingOrder]):
        """미체결 주문 리스트를 테이블에 표시"""
        t = self.table
        t.clearContents()

        if not working_orders:
            t.setRowCount(0)
            return

        t.setRowCount(len(working_orders))

        for row, wo in enumerate(working_orders):
            # 색상: BUY=빨강, SELL=파랑
            is_buy = (wo.side == Side.BUY or str(wo.side).upper() == "BUY")
            color = QtGui.QColor("red") if is_buy else QtGui.QColor("blue")

            # 종목은 WorkingOrder 에 없으면 나중에 symbol 필드 추가해서 쓰면 됨
            symbol = getattr(wo, "symbol", "")

            # 주문 시간
            import time
            tm_str = ""
            if wo.created_at:
                tm_str = time.strftime("%H:%M:%S", time.localtime(wo.created_at))

            items = [
                QTableWidgetItem(str(wo.id)),           # 주문ID
                QTableWidgetItem(symbol),               # 종목
                QTableWidgetItem(wo.side.name),        # 매도/매수 (Side enum 기준)
                QTableWidgetItem(f"{wo.price:,.2f}"),  # 가격
                QTableWidgetItem(str(wo.qty)),         # 총수량
                QTableWidgetItem(str(wo.remaining)),   # 잔량
                QTableWidgetItem(tm_str),              # 주문시간
            ]

            for col, item in enumerate(items):
                if col in (0, 1, 2, 6):  # ID, 종목, 방향, 시간
                    align = QtAlignCenter
                else:                    # 가격, 수량, 잔량
                    align = QtAlignRight | QtAlignVCenter
                item.setTextAlignment(align)
                if col in (2, 3, 4, 5):  # 방향/가격/수량/잔량에 색 적용
                    item.setForeground(QtGui.QBrush(color))

                t.setItem(row, col, item)

        t.resizeColumnsToContents()
