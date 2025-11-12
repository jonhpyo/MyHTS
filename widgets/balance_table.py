# widgets/balance_table.py

from widgets.ui_styles import apply_header_style, BLUE_HEADER
from .ui_styles import QtAlignCenter, QtAlignRight, QtAlignVCenter

try:
    from PyQt6 import QtWidgets, QtGui, QtCore
    from PyQt6.QtCore import Qt
    _QT6 = True
except Exception:
    from PyQt5 import QtWidgets, QtGui, QtCore
    from PyQt5.QtCore import Qt
    _QT6 = False


from services.account_service import AccountState   # 기존처럼 사용


class BalanceTable:
    """
    잔고 탭 구성:
      - 상단: 계좌 요약 테이블 (summary_table)
      - 하단: 종목별 포지션 테이블 (positions_table)
    """

    def __init__(self, summary_table: QtWidgets.QTableWidget, max_positions: int = 50):
        self.summary_table = summary_table
        self.max_positions = max_positions
        self.positions_table: QtWidgets.QTableWidget | None = None

        self._init_summary_ui()
        self._ensure_positions_table()

    # -------------------------------------------------
    # 상단 요약 테이블 구성
    # -------------------------------------------------
    def _init_summary_ui(self):
        t = self.summary_table
        t.clear()


        # 항목들: 필요에 따라 추가/수정 가능
        headers = [
            "총자산(Total Equity)",
            "현금(Cash)",
            "평가금액(Asset Value)",
            "실현손익(Realized P/L)",
            "미실현손익(Unrealized P/L)",
            "총손익(Total P/L)",
        ]
        t.setRowCount(1)
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)

        # 편집/선택 막기
        if hasattr(QtWidgets.QAbstractItemView, "EditTrigger"):
            t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        else:
            t.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            t.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

        apply_header_style(t, BLUE_HEADER)
        t.horizontalHeader().setStretchLastSection(True)
        t.horizontalHeader().setMinimumSectionSize(80)
        t.setFixedHeight(60)  # 요약바 높이 고정

        apply_header_style(t, BLUE_HEADER)
        t.resizeColumnsToContents()

    # -------------------------------------------------
    # 하단 포지션 테이블 생성
    # -------------------------------------------------
    def _ensure_positions_table(self):
        """
        잔고 탭 페이지 레이아웃 안에 포지션 테이블을 하나 더 만든다.
        summary_table 의 parent 위젯 아래에 붙인다.
        """
        parent = self.summary_table.parent()
        if parent is None:
            return

        layout = parent.layout()
        if layout is None:
            layout = QtWidgets.QVBoxLayout(parent)
            parent.setLayout(layout)

            # 요약 테이블이 레이아웃에 아직 안 올라가 있다면 추가
            if self.summary_table.parent() is parent and self.summary_table not in [layout.itemAt(i).widget() for i in range(layout.count())]:
                layout.addWidget(self.summary_table)

        # 포지션 테이블이 이미 있으면 재사용
        existing = parent.findChild(QtWidgets.QTableWidget, "tab_positions_table")
        if existing:
            self.positions_table = existing
            return

        # 새 포지션 테이블 생성
        pos_table = QtWidgets.QTableWidget(parent)
        pos_table.setObjectName("tab_positions_table")
        layout.addWidget(pos_table)
        self.positions_table = pos_table

        self._init_positions_ui()

    def _init_positions_ui(self):
        t = self.positions_table
        if t is None:
            return

        headers = ["종목", "수량", "평균단가", "현재가", "평가금액", "평가손익"]
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)

        if hasattr(QtWidgets.QAbstractItemView, "EditTrigger"):
            t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
            t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        else:
            t.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            t.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        if hasattr(t.horizontalHeader(), "setStretchLastSection"):
            t.horizontalHeader().setStretchLastSection(True)

        apply_header_style(t, BLUE_HEADER)

    # -------------------------------------------------
    # 렌더: AccountState -> 요약 + 포지션
    # -------------------------------------------------
    def render(self, state):
        """AccountState 기준으로 상단 요약 갱신"""
        cash = float(getattr(state, "cash", 0.0))
        asset_value = float(getattr(state, "asset_value", 0.0))
        realized_pnl = float(getattr(state, "realized_pnl", 0.0))
        unrealized_pnl = float(getattr(state, "unrealized_pnl", 0.0))
        total_equity = cash + asset_value
        total_pnl = realized_pnl + unrealized_pnl

        values = [
            total_equity,
            cash,
            asset_value,
            realized_pnl,
            unrealized_pnl,
            total_pnl,
        ]

        for c, val in enumerate(values):
            item = QtWidgets.QTableWidgetItem(f"{val:,.2f}")
            item.setTextAlignment(QtAlignCenter | QtAlignRight)

            # 🔹 손익 색상 처리
            if c in (3, 4, 5):  # 손익 계열 컬럼
                color = QtGui.QColor("red") if val > 0 else (
                    QtGui.QColor("blue") if val < 0 else QtGui.QColor("black")
                )
                item.setForeground(QtGui.QBrush(color))

            self.summary_table.setItem(0, c, item)

        self.summary_table.resizeColumnsToContents()

        # ---------- 2) 하단 포지션 ----------
        t = self.positions_table
        if t is None:
            return

        # positions: [Position(symbol, qty, avg_price, last_price, ...)] 라고 가정
        positions = getattr(state, "positions", None)

        t.clearContents()
        if not positions:
            t.setRowCount(0)
            return

        rows = min(len(positions), self.max_positions)
        t.setRowCount(rows)

        for i, pos in enumerate(positions[:rows]):
            symbol = getattr(pos, "symbol", "")
            qty = float(getattr(pos, "qty", 0.0))
            avg_price = float(getattr(pos, "avg_price", 0.0))
            last_price = float(getattr(pos, "last_price", avg_price or 0.0))

            value = qty * last_price
            pnl = (last_price - avg_price) * qty

            data = [
                symbol,
                f"{qty:,.4f}",
                f"{avg_price:,.2f}",
                f"{last_price:,.2f}",
                f"{value:,.2f}",
                f"{pnl:,.2f}",
            ]

            for c, text in enumerate(data):
                item = QtWidgets.QTableWidgetItem(text)
                if c == 0:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)

                # 평가손익 컬럼 색상
                # 평가손익 컬럼 색상
                if c == 5:  # 6번째 컬럼: 평가손익
                    try:
                        pnl_val = float(text.replace(",", ""))
                        if pnl_val > 0:
                            color = QtGui.QColor("red")
                        elif pnl_val < 0:
                            color = QtGui.QColor("blue")
                        else:
                            color = QtGui.QColor("black")
                        item.setForeground(QtGui.QBrush(color))
                    except Exception:
                        pass

                t.setItem(i, c, item)

        t.resizeColumnsToContents()
