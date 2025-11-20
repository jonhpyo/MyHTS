# widgets/open_account_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox
)
from controllers.account_controller_api import AccountControllerAPI


class OpenAccountDialog(QDialog):
    """
    계좌 개설 다이얼로그 (API 기반 V2)
    - 이메일 입력 필요 없음 (로그인한 user_id 사용)
    """

    def __init__(self, user_id: int, accountApi: AccountControllerAPI, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.accountApi = accountApi

        self.setWindowTitle("계좌 개설")

        layout = QFormLayout(self)

        # 계좌 별칭만 입력받음
        self.edit_name = QLineEdit()

        layout.addRow("계좌 이름(별칭)", self.edit_name)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.on_accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    # ------------------------------------------
    # 계좌 개설 실행
    # ------------------------------------------
    def on_accept(self):
        try:
            name = self.edit_name.text().strip()
            if not name:
                QMessageBox.warning(self, "입력 오류", "계좌 이름을 입력하세요.")
                return

            # 계좌번호는 서버에서 생성됨
            account_id = self.accountApi.open_account(
                user_id=self.user_id,
                account_no=name   # ← FastAPI는 account_no 필드이름이지만 의미는 alias용
            )

            if account_id is None:
                QMessageBox.warning(self, "오류", "계좌 개설 실패")
                return

            QMessageBox.information(
                self,
                "성공",
                f"새 계좌가 개설되었습니다.\n계좌 ID = {account_id}"
            )
            self.accept()

        except Exception as e:
            print("[OpenAccountDialog] error:", e)
            QMessageBox.warning(self, "오류", "계좌 개설 중 오류 발생")
