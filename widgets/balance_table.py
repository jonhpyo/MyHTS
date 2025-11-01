# widgets/balance_table.py
from widgets.ui_styles import apply_header_style, BLUE_HEADER

try:
    from PyQt6 import QtWidgets
    from PyQt6.QtCore import Qt
    _QT6 = True
except Exception:
    from PyQt5 import QtWidgets
    from PyQt5.QtCore import Qt
    _QT6 = False

from services.account_service import AccountService, AccountState

class BalanceTable:
    """Cash/Position 등을 간단히 보여주는 테이블."""
    def __init__(self, table: QtWidgets.QTableWidget, max_rows: int = 30):
        self.table = table
        self.max_rows = max_rows
        self._init_ui()

    def _init_ui(self):
        t = self.table
        t.setColumnCount(2)
        t.setRowCount(3)  # Cash, Position, Avg Price
        t.setHorizontalHeaderLabels(["항목", "값"])
        t.verticalHeader().setVisible(False)
        if hasattr(QtWidgets.QAbstractItemView, "EditTrigger"):
            t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        else:
            t.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            t.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

        t.setItem(0, 0, QtWidgets.QTableWidgetItem("현금(Cash)"))
        t.setItem(1, 0, QtWidgets.QTableWidgetItem("포지션(Position)"))
        t.setItem(2, 0, QtWidgets.QTableWidgetItem("평균단가(Avg Price)"))


    def render(self, state: AccountState):
        self.table.setItem(0, 1, QtWidgets.QTableWidgetItem(f"{state.cash:,.2f}"))
        self.table.setItem(1, 1, QtWidgets.QTableWidgetItem(str(state.position)))
        self.table.setItem(2, 1, QtWidgets.QTableWidgetItem(f"{state.avg_price:,.2f}"))
        self.table.resizeColumnsToContents()
        apply_header_style(self.table, BLUE_HEADER)
