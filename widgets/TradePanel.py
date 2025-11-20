# widgets/trade_panel.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt


class TradePanel(QWidget):
    def __init__(self, trades_widget, parent=None):
        super().__init__(parent)

        self.original_parent = None
        self.original_layout = None
        self.original_index = None
        self.is_maximized = False

        self.trades_widget = trades_widget  # 기존 체결 테이블 위젯

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 상단 타이틀 + 버튼 영역
        top = QHBoxLayout()
        title = QLabel("체결현황")
        title.setStyleSheet("font-size:18px; font-weight:600;")

        self.btn_toggle = QPushButton("⛶")  # 또는 ⬜
        self.btn_toggle.setFixedWidth(30)
        self.btn_toggle.clicked.connect(self.toggle_maximize)

        top.addWidget(title)
        top.addStretch()
        top.addWidget(self.btn_toggle)

        layout.addLayout(top)
        layout.addWidget(trades_widget)

    # ---------------------------------------------------
    def toggle_maximize(self):
        win = self.window()

        if not self.is_maximized:
            # 현재 부모 정보 저장
            self.original_parent = self.parent()
            self.original_layout = self.parent().layout()
            self.original_index = self.original_layout.indexOf(self)

            # 부모에서 제거
            self.setParent(None)

            # 메인윈도우의 중앙에 단독 표시
            win.setCentralWidget(self)

            self.btn_toggle.setText("🗗")  # 복원 버튼 아이콘
            self.is_maximized = True

        else:
            # 중앙 위젯 비우기
            win.takeCentralWidget()

            # 기존 위치로 복귀
            self.original_layout.insertWidget(self.original_index, self)
            self.btn_toggle.setText("⛶")

            self.is_maximized = False
