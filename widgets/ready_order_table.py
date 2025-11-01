# widgets/ready_orders_table.py
from typing import List, Any

# PyQt6 우선, 실패 시 PyQt5 폴백
try:
    from PyQt6 import QtWidgets, QtGui, QtCore
    QtAlignCenter = QtCore.Qt.AlignmentFlag.AlignCenter
    QtAlignRight  = QtCore.Qt.AlignmentFlag.AlignRight
    QtAlignVCenter = QtCore.Qt.AlignmentFlag.AlignVCenter
except Exception:
    from PyQt5 import QtWidgets, QtGui, QtCore
    QtAlignCenter = QtCore.Qt.AlignCenter
    QtAlignRight  = QtCore.Qt.AlignRight
    QtAlignVCenter = QtCore.Qt.AlignVCenter

from widgets.ui_styles import apply_header_style, BLUE_HEADER


class ReadyOrdersTable:
    """
    미체결(대기) 주문 테이블 위젯 래퍼.
    - render(orders)로 전체 갱신
    - orders 원소는 dataclass(WorkingOrder) 또는 dict 모두 지원
      (id, time, type, side, price, qty, status 필드/키 사용)
    """
    COLUMNS = ["시간", "주문ID", "종류", "Side", "가격", "수량", "상태"]

    def __init__(self, table: QtWidgets.QTableWidget):
        self.table = table
        self._init_ui()

    def _init_ui(self):
        t = self.table
        t.setObjectName(t.objectName() or "tap_ready_trades")
        t.setColumnCount(len(self.COLUMNS))
        t.setHorizontalHeaderLabels(self.COLUMNS)
        t.verticalHeader().setVisible(False)
        # 읽기 전용 & 행 선택
        if hasattr(QtWidgets.QAbstractItemView, "EditTrigger"):
            t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        else:
            t.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        t.horizontalHeader().setStretchLastSection(False)
        apply_header_style(t, BLUE_HEADER)

    def render(self, orders: List[Any]):
        t = self.table
        rows = orders or []
        t.setRowCount(len(rows))

        for r, od in enumerate(rows):
            # dataclass/obj/dict 모두 대응
            get = (lambda k, d=None: getattr(od, k, d)) if not isinstance(od, dict) else (lambda k, d=None: od.get(k, d))

            time  = get("time", "")
            oid   = get("id", "")
            otype = get("type", "LMT")
            side  = get("side", "")
            price = float(get("price", 0.0) or 0.0)
            qty   = int(get("qty", 0) or 0)
            stat  = get("status", "WORKING")

            t.setItem(r, 0, QtWidgets.QTableWidgetItem(str(time)))
            t.setItem(r, 1, QtWidgets.QTableWidgetItem(str(oid)))
            t.setItem(r, 2, QtWidgets.QTableWidgetItem(str(otype)))
            t.setItem(r, 3, QtWidgets.QTableWidgetItem(str(side)))

            it_price = QtWidgets.QTableWidgetItem(f"{price:,.2f}")
            it_qty   = QtWidgets.QTableWidgetItem(f"{qty:,}")
            it_price.setTextAlignment(QtAlignRight | QtAlignVCenter)
            it_qty.setTextAlignment(QtAlignRight | QtAlignVCenter)

            t.setItem(r, 4, it_price)
            t.setItem(r, 5, it_qty)
            t.setItem(r, 6, QtWidgets.QTableWidgetItem(str(stat)))

        t.resizeColumnsToContents()
