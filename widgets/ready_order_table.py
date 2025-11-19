# widgets/ready_order_table.py (V2 API 기반 리팩토링)
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
from PyQt6.QtCore import Qt
from widgets.ui_styles import BLUE_HEADER, apply_header_style, QtAlignCenter, QtAlignRight, QtAlignVCenter


class ReadyOrdersTable:
    """
    미체결 주문 테이블 (API 기반 V2)
    - 체크박스 포함
    - get_checked_order_ids() 제공
    - DB/REST API에서 받아온 row 포맷을 자동 처리
    """

    HEADERS = ["", "주문ID", "종목", "매수/매도", "가격", "주문수량", "잔량", "시간"]

    def __init__(self, table: QTableWidget):
        self.table = table
        self._init_ui()

    # --------------------------------------------------------
    # UI 초기화
    # --------------------------------------------------------
    def _init_ui(self):
        t = self.table
        t.setColumnCount(len(self.HEADERS))
        t.setHorizontalHeaderLabels(self.HEADERS)
        t.verticalHeader().setVisible(False)

        # 스타일
        apply_header_style(t, BLUE_HEADER)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

    # --------------------------------------------------------
    # 렌더링
    # --------------------------------------------------------
    def render_from_api(self, rows):
        """
        rows =
          case1: [{"id":1, "symbol":"SOL", ...}, ...]  ← dict
          case2: [(1, "SOL", "BUY", 100, 10, 5, "2025-01-01"), ...] ← tuple/list
        """
        t = self.table
        t.clearContents()

        if not rows:
            t.setRowCount(0)
            return

        t.setRowCount(len(rows))

        for r, row in enumerate(rows):
            try:
                # ------------------------------
                # 1) dict 타입
                # ------------------------------
                if isinstance(row, dict):
                    oid = row.get("id", "")
                    symbol = row.get("symbol", "")
                    side = str(row.get("side", "")).upper()
                    price = float(row.get("price", 0.0))
                    qty = float(row.get("qty", 0.0))
                    remain = float(row.get("remaining_qty", 0.0))
                    created = row.get("created_at", "")

                # ------------------------------
                # 2) list/tuple 타입 (컬럼 순서 예상)
                # ------------------------------
                else:
                    # 예: SELECT id, symbol, side, price, qty, remaining_qty, created_at
                    (
                        oid,
                        symbol,
                        side,
                        price,
                        qty,
                        remain,
                        created,
                    ) = row

                    side = str(side).upper()
                    price = float(price)
                    qty = float(qty)
                    remain = float(remain)

                # =============================
                # 체크박스
                # =============================
                chk = QCheckBox()
                chk_widget = QtWidgets.QWidget()
                layout = QtWidgets.QHBoxLayout(chk_widget)
                layout.addWidget(chk)
                layout.setAlignment(QtAlignVCenter)
                layout.setContentsMargins(0, 0, 0, 0)
                t.setCellWidget(r, 0, chk_widget)

                # =============================
                # 일반 항목들
                # =============================
                items = [
                    QTableWidgetItem(str(oid)),
                    QTableWidgetItem(symbol),
                    QTableWidgetItem(side),
                    QTableWidgetItem(f"{price:,.2f}"),
                    QTableWidgetItem(f"{qty:,.4f}"),
                    QTableWidgetItem(f"{remain:,.4f}"),
                    QTableWidgetItem(str(created)),
                ]

                for c, item in enumerate(items, start=1):
                    if c in (4, 5, 6):
                        item.setTextAlignment(QtAlignRight | QtAlignVCenter)
                    else:
                        item.setTextAlignment(QtAlignCenter)
                    t.setItem(r, c, item)

            except Exception as e:
                print("[ReadyOrdersTable] row render error:", e)

        apply_header_style(t, BLUE_HEADER)

    # --------------------------------------------------------
    # 선택된 주문 조회
    # --------------------------------------------------------
    def get_checked_order_ids(self):
        """체크된 row 의 order_id 리스트 반환"""
        ids = []
        t = self.table

        for r in range(t.rowCount()):
            widget = t.cellWidget(r, 0)
            if widget:
                chk = widget.findChild(QCheckBox)
                if chk and chk.isChecked():
                    oid_item = t.item(r, 1)  # 주문ID
                    if oid_item:
                        try:
                            ids.append(int(oid_item.text()))
                        except:
                            pass

        return ids
