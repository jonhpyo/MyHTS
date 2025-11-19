# widgets/trades_table.py (V2 API 기반 리팩토링)
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt
from widgets.ui_styles import BLUE_HEADER, apply_header_style, QtAlignCenter, QtAlignRight, QtAlignVCenter


class TradesTable:
    """
    체결내역 테이블 (API 기반 V2)
    - render_from_api() 로만 갱신
    - add_fill() 로 UI에 직접 체결 추가 가능 (강조 색상)
    """

    HEADERS = ["계좌번호", "종목", "매도/매수", "체결가", "체결수량", "시간", "비고"]

    def __init__(self, table: QTableWidget, max_rows: int = 30):
        self.table = table
        self.max_rows = max_rows
        self.trades = []  # dict 리스트로 관리
        self._init_ui()

    # ---------------------------------------------------
    # UI 초기화
    # ---------------------------------------------------
    def _init_ui(self):
        t = self.table
        t.setColumnCount(len(self.HEADERS))
        t.setHorizontalHeaderLabels(self.HEADERS)
        t.verticalHeader().setVisible(False)
        apply_header_style(t, BLUE_HEADER)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

    # ---------------------------------------------------
    # API 기반 체결 렌더링
    # ---------------------------------------------------
    def render_from_api(self, rows):
        """
        rows: [
          {
            "account_no": "1000001",
            "symbol": "SOLUSDT",
            "side": "BUY",
            "price": 108.2,
            "quantity": 4.0,
            "trade_time": "2025-11-19T09:12:54",
            "remark": ""
          },
          ...
        ]
        """
        t = self.table
        t.clearContents()

        if not rows:
            t.setRowCount(0)
            return

        # 메모리 저장
        self.trades = list(rows)[0:self.max_rows]
        t.setRowCount(len(self.trades))

        for row, tr in enumerate(self.trades):
            try:
                account_no = tr.get("account_no", "")
                symbol = tr.get("symbol", "")
                side = str(tr.get("side", "")).upper()
                price = float(tr.get("price", 0.0))
                qty = float(tr.get("quantity", 0.0))
                trade_time = tr.get("trade_time", "")
                remark = tr.get("remark", "")

                # 색상 (매수: 빨강, 매도: 파랑)
                fg_color = QtGui.QColor("red") if side == "BUY" else QtGui.QColor("blue")

                items = [
                    QTableWidgetItem(account_no),
                    QTableWidgetItem(symbol),
                    QTableWidgetItem(side),
                    QTableWidgetItem(f"{price:,.2f}"),
                    QTableWidgetItem(f"{qty:,.4f}"),
                    QTableWidgetItem(self._format_time(trade_time)),
                    QTableWidgetItem(remark),
                ]

                for col, item in enumerate(items):
                    if col in (3, 4):  # 가격, 수량 우측 정렬
                        item.setTextAlignment(QtAlignRight | QtAlignVCenter)
                    else:
                        item.setTextAlignment(QtAlignCenter)

                    # BUY/SELL 색 입히기
                    if col in (2, 3, 4):
                        item.setForeground(QtGui.QBrush(fg_color))

                    t.setItem(row, col, item)

            except Exception as e:
                print("[TradesTable] render_from_api row error:", e)

        apply_header_style(self.table, BLUE_HEADER)

    # ---------------------------------------------------
    # 내 주문 체결을 UI에 직접 추가 (배경/볼드 강조)
    # ---------------------------------------------------
    def add_fill(self, side: str, price: float, qty: int, symbol: str = "", account_no: str = "my"):
        """
        내 체결을 UI에 직접 추가할 때 사용.
        - 추가된 레코드는 강한 강조 표시 (연노랑 BG, Bold)
        - API 체결과 혼합 가능
        """
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")

        side = side.upper()
        fg_color = QtGui.QColor("red") if side == "BUY" else QtGui.QColor("blue")

        new_row = {
            "account_no": account_no,
            "symbol": symbol,
            "side": side,
            "price": price,
            "quantity": qty,
            "trade_time": now,
            "remark": "",
            "is_fill": True
        }

        # 최상단에 삽입
        self.trades.insert(0, new_row)
        self.trades = self.trades[: self.max_rows]
        self._render_internal()

    # ---------------------------------------------------
    # 내부 렌더링 (add_fill용)
    # ---------------------------------------------------
    def _render_internal(self):
        t = self.table
        t.clearContents()
        t.setRowCount(len(self.trades))

        for row, tr in enumerate(self.trades):
            try:
                acc = tr.get("account_no", "")
                symbol = tr.get("symbol", "")
                side = tr.get("side", "")
                price = float(tr.get("price", 0.0))
                qty = float(tr.get("quantity", 0.0))
                ttime = tr.get("trade_time", "")
                remark = tr.get("remark", "")
                is_fill = tr.get("is_fill", False)

                fg_color = QtGui.QColor("red") if side == "BUY" else QtGui.QColor("blue")

                items = [
                    QTableWidgetItem(acc),
                    QTableWidgetItem(symbol),
                    QTableWidgetItem(side),
                    QTableWidgetItem(f"{price:,.2f}"),
                    QTableWidgetItem(f"{qty:,.4f}"),
                    QTableWidgetItem(self._format_time(ttime)),
                    QTableWidgetItem(remark),
                ]

                for col, item in enumerate(items):
                    if col in (3, 4):
                        item.setTextAlignment(QtAlignRight | QtAlignVCenter)
                    else:
                        item.setTextAlignment(QtAlignCenter)

                    if col in (2, 3, 4):
                        item.setForeground(QtGui.QBrush(fg_color))

                    # 강조된 체결 (내 주문 체결)
                    if is_fill:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                        bg = QtGui.QColor(255, 255, 200)
                        item.setBackground(QtGui.QBrush(bg))

                    t.setItem(row, col, item)

            except Exception as e:
                print("[TradesTable] _render_internal row error:", e)

        apply_header_style(self.table, BLUE_HEADER)

    # ---------------------------------------------------
    def _format_time(self, t):
        """API가 datetime 또는 str을 줄 수 있으므로 안전하게 처리"""
        if hasattr(t, "strftime"):
            return t.strftime("%H:%M:%S")
        if "T" in str(t):
            try:
                return str(t).split("T")[1][:8]
            except:
                return str(t)
        return str(t)
