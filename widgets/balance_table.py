# widgets/balance_table.py
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox


from widgets.ui_styles import BLUE_HEADER, apply_header_style, QtAlignCenter, QtAlignRight, QtAlignVCenter


class BalanceTable:
    """계좌 잔고 + 포지션 테이블"""

    def __init__(self, table: QtWidgets.QTableWidget):
        self.table = table
        self._init_ui()

    def _init_ui(self):
        t = self.table
        headers = ["종목", "보유수량", "평균단가", "현재가", "평가금액", "평가손익(₩)"]
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        apply_header_style(t, BLUE_HEADER)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        t.setAlternatingRowColors(True)

        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        apply_header_style(self.table, BLUE_HEADER)

        # 현금/총평가금액 표시
    def render_summary(self, balance: float, total_pl: float):
        """상단 제목줄을 갱신하거나 별도 QLabel에 표시"""
        # print(f"[BalanceTable] 💰현금: {balance:,.0f} / 평가손익합계: {total_pl:+,.0f}")
        print('--balance--line:34')

    def render_from_summary(self, summary: dict, md_service):
        """
        summary:
            {
                "balance": float,
                "positions": [
                    {"symbol": "AAPL", "qty": 1.0, "avg_price": 100.0},
                    ...
                ]
            }

        md_service:
            MarketDataService — get_last_price(symbol) 지원해야 함
        """

        positions = summary.get("positions", [])
        cash = float(summary.get("balance", 0.0))

        # 1) 심볼별 현재가 수집
        prices = {}

        for p in positions:
            sym = p["symbol"]

            last_price = None
            if hasattr(md_service, "get_last_price"):
                try:
                    last_price = md_service.get_last_price(sym)
                except:
                    last_price = None

            if last_price is None:
                last_price = p.get("avg_price", 0.0)

            prices[sym] = float(last_price)

        # 2) 포지션 테이블 렌더링
        self.render_positions(positions, prices)

        # 3) 현금 + 총손익 출력
        total_eval = sum(p["qty"] * prices.get(p["symbol"], p["avg_price"]) for p in positions)
        total_pl = sum(
            (prices.get(p["symbol"], p["avg_price"]) - p["avg_price"]) * p["qty"]
            for p in positions
        )

        self.render_summary(cash, total_pl)

    def render_positions(self, positions, prices: dict[str, float]):
        """
        positions: DBService.get_account_summary()['positions']
        prices: {symbol: 현재가} from MarketDataService
        """
        # print('---------------------------------')
        # print('render_positions')
        t = self.table
        t.clearContents()
        if not positions:
            t.setRowCount(0)
            return

        t.setRowCount(len(positions))

        total_pl = 0.0
        for row, pos in enumerate(positions):
            symbol = pos["symbol"]
            qty = float(pos["qty"])
            avg_price = float(pos["avg_price"])
            cur_price = float(prices.get(symbol, avg_price))
            eval_value = qty * cur_price
            pl = (cur_price - avg_price) * qty
            total_pl += pl

            # 색상: 손익 플러스=빨강, 마이너스=파랑
            color = QtGui.QColor("red") if pl > 0 else QtGui.QColor("blue")

            items = [
                QtWidgets.QTableWidgetItem(symbol),
                QtWidgets.QTableWidgetItem(f"{qty:,.4f}"),
                QtWidgets.QTableWidgetItem(f"{avg_price:,.2f}"),
                QtWidgets.QTableWidgetItem(f"{cur_price:,.2f}"),
                QtWidgets.QTableWidgetItem(f"{eval_value:,.0f}"),
                QtWidgets.QTableWidgetItem(f"{pl:+,.0f}"),
            ]

            for c, item in enumerate(items):
                if c in (1, 2, 3, 4, 5):
                    item.setTextAlignment(QtAlignRight | QtAlignVCenter)
                else:
                    item.setTextAlignment(QtAlignCenter)
                if c == 5:
                    item.setForeground(QtGui.QBrush(color))
                t.setItem(row, c, item)

        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        apply_header_style(self.table, BLUE_HEADER)

        self.render_summary(sum([float(p["qty"]) * prices.get(p["symbol"], p["avg_price"]) for p in positions]), total_pl)

