
# widgets/ready_order_table.py
try:
    from PyQt6 import QtWidgets, QtGui, QtCore
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox

    _QT6 = True
except Exception:
    from PyQt5 import QtWidgets, QtGui, QtCore
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
    _QT6 = False

from .ui_styles import QtAlignCenter, QtAlignRight, QtAlignVCenter
from .ui_styles import BLUE_HEADER, DARK_HEADER, apply_header_style

from models.working_order import WorkingOrder
from models.order import Side


class ReadyOrdersTable:
    """미체결 주문(WorkingOrder) 리스트를 표시하는 테이블"""

    def __init__(self, table: QTableWidget):
        self.table = table
        self._init_ui()

    def _init_ui(self):
        t = self.table
        headers = ["선택", "주문ID", "종목", "매도/매수", "가격", "총수량", "잔량", "주문시간"]
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        apply_header_style(t, BLUE_HEADER)
        t.verticalHeader().setVisible(False)

        if _QT6:
            t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.AllEditTriggers)
            t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
            t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        else:
            t.setEditTriggers(QtWidgets.QAbstractItemView.AllEditTriggers)
            t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            t.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)


    def get_selected_order_ids(self) -> list[int]:
        """테이블에서 선택된 행들의 주문ID 리스트 반환"""
        t = self.table
        ids: set[int] = set()

        sel_model = t.selectionModel()
        if not sel_model:
            return []

        for index in sel_model.selectedRows():  # 행 단위 선택
            row = index.row()
            item = t.item(row, 0)  # 0번 컬럼 = 주문ID
            if item:
                try:
                    ids.add(int(item.text()))
                except ValueError:
                    pass

        return sorted(ids)

    def get_checked_order_ids(self) -> list[int]:
        """맨 앞 체크박스가 체크된 행들의 주문ID 리스트 반환"""
        t = self.table
        ids: list[int] = []

        row_count = t.rowCount()
        print('-------------------------------')
        print(row_count)
        print('-------------------------------')
        for row in range(row_count):
            # chk = t.item(row, 0)  # 체크박스 아이템
            chk = t.cellWidget(row, 0)
            if not isinstance(chk, QtWidgets.QCheckBox):
                continue
            if not chk.isChecked():
                continue

            id_item = t.item(row, 1)  # 1번 컬럼 = 주문ID
            if not id_item:
                continue
            try:
                ids.append(int(id_item.text()))
            except ValueError:
                pass

        return ids

    # def render(self, working_orders: list[WorkingOrder]):
    #     """미체결 주문 리스트를 테이블에 표시"""
    #     t = self.table
    #     t.clearContents()
    #
    #     if not working_orders:
    #         t.setRowCount(0)
    #         return
    #
    #     t.setRowCount(len(working_orders))
    #
    #     for row, wo in enumerate(working_orders):
    #         # 색상: BUY=빨강, SELL=파랑
    #         is_buy = (wo.side == Side.BUY or str(wo.side).upper() == "BUY")
    #         color = QtGui.QColor("red") if is_buy else QtGui.QColor("blue")
    #
    #         # 종목은 WorkingOrder 에 없으면 나중에 symbol 필드 추가해서 쓰면 됨
    #         symbol = getattr(wo, "symbol", "")
    #
    #         # 주문 시간
    #         import time
    #         tm_str = ""
    #         if wo.created_at:
    #             tm_str = time.strftime("%H:%M:%S", time.localtime(wo.created_at))
    #
    #         # ✅ 0번 컬럼: QCheckBox 위젯
    #         chk = QCheckBox()
    #         chk.setChecked(False)
    #         chk.setStyleSheet("margin-left:auto; margin-right:auto;")
    #         chk.isEnabled()
    #         t.setCellWidget(row, 0, chk)
    #
    #         items = [
    #             QTableWidgetItem(str(wo.id)),          # 주문ID
    #             QTableWidgetItem(symbol),              # 종목
    #             QTableWidgetItem(wo.side.side),        # 매도/매수 (Side enum 기준)
    #             QTableWidgetItem(f"{wo.price:,.2f}"),  # 가격
    #             QTableWidgetItem(str(wo.qty)),         # 총수량
    #             QTableWidgetItem(str(wo.remaining)),   # 잔량
    #             QTableWidgetItem(tm_str),              # 주문시간
    #         ]
    #
    #         for col, item in enumerate(items, start=1):
    #             if col in (1, 2, 3, 7):  # ID, 종목, 방향, 시간
    #                 align = QtAlignCenter
    #             else:                    # 가격, 수량, 잔량
    #                 align = QtAlignRight | QtAlignVCenter
    #             item.setTextAlignment(align)
    #
    #             if col in (3, 4, 5, 6):  # 방향/가격/수량/잔량에 색 적용
    #                 item.setForeground(QtGui.QBrush(color))
    #
    #             t.setItem(row, col, item)
    #
    #     t.resizeColumnsToContents()
    #     t.setColumnWidth(0, 24)

    def render_from_db(self, rows):
        """
        DB에서 읽은 미체결 주문 리스트를 테이블에 표시.
        기대 컬럼:
          id, symbol, side, price, qty, remaining_qty, created_at
        (psycopg2.extras.DictRow 또는 dict/tuple 모두 대응)
        """
        t = self.table
        t.clearContents()

        if not rows:
            t.setRowCount(0)
            return

        t.setRowCount(len(rows))

        import datetime

        for r, row in enumerate(rows):
            # DictRow / dict / tuple 모두 처리
            try:
                if hasattr(row, "keys"):  # DictRow or dict
                    oid      = row.get("id")
                    symbol   = row.get("symbol", "")
                    side     = str(row.get("side", "")).upper()
                    price    = float(row.get("price", 0.0))
                    qty      = float(row.get("qty", 0.0))
                    remaining= float(row.get("remaining_qty", 0.0))
                    ctime    = row.get("created_at")
                else:
                    # SELECT id, symbol, side, price, qty, remaining_qty, created_at 순서라고 가정
                    oid, symbol, side, price, qty, remaining, ctime = row
                    side = str(side).upper()
                    price = float(price)
                    qty = float(qty)
                    remaining = float(remaining)

                # 주문 시간 문자열
                if isinstance(ctime, (datetime.datetime, datetime.time)):
                    tm_str = ctime.strftime("%H:%M:%S")
                else:
                    tm_str = str(ctime or "")

                # 색상: BUY=빨강, SELL=파랑
                color = QtGui.QColor("red") if side == "BUY" else QtGui.QColor("blue")

                chk = QCheckBox()
                chk.setChecked(False)

                chk.setStyleSheet("margin-left:auto; margin-right:auto;")
                t.setCellWidget(r, 0, chk)

                items = [
                    QTableWidgetItem(str(oid)),              # 주문ID
                    QTableWidgetItem(symbol),                # 종목
                    QTableWidgetItem(side),                  # 매도/매수
                    QTableWidgetItem(f"{price:,.2f}"),       # 가격
                    QTableWidgetItem(f"{qty:,.4f}"),         # 총수량
                    QTableWidgetItem(f"{remaining:,.4f}"),   # 잔량
                    QTableWidgetItem(tm_str),                # 주문시간
                ]

                for col, item in enumerate(items, start=1):
                    if col in (1, 2, 3, 7):  # ID, 종목, 방향, 시간
                        align = QtAlignCenter
                    else:                    # 가격, 수량, 잔량
                        align = QtAlignRight | QtAlignVCenter
                    item.setTextAlignment(align)

                    if col in (3, 4, 5, 6):
                        item.setForeground(QtGui.QBrush(color))

                    # ✅ 편집 불가로 플래그 조정
                    flags = item.flags()
                    if _QT6:
                        flags &= ~Qt.ItemFlag.ItemIsEditable
                    else:
                        flags &= ~Qt.ItemIsEditable
                    item.setFlags(flags)

                    t.setItem(r, col, item)

            except Exception as e:
                print(f"[ReadyOrdersTable] row {r} render error:", e)
                continue

        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        apply_header_style(self.table, BLUE_HEADER)
