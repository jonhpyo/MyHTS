# widgets/open_account_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox
)
from services.db_service import DBService


class OpenAccountDialog(QDialog):
    def __init__(self, db: DBService, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("계좌 개설")

        layout = QFormLayout(self)

        # 간단하게: 이메일 + 계좌 이름만 받자
        self.edit_email = QLineEdit()
        self.edit_name = QLineEdit()

        layout.addRow("이메일", self.edit_email)
        layout.addRow("계좌 이름(별칭)", self.edit_name)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.on_accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    def on_accept(self):
        try:
            email = self.edit_email.text()
            email = self.edit_email.text().strip()
            name = self.edit_name.text().strip()

            if not email:
                QMessageBox.warning(self, "입력 오류", "이메일을 입력하세요.")
                return

            user_id = self.db.get_user_id_by_email(email)
            if user_id is None:
                QMessageBox.warning(self, "오류", "해당 이메일의 회원이 없습니다.")
                return

            account_no = self.db.create_account(user_id, name)
            if account_no is None:
                QMessageBox.warning(self, "오류", "계좌 개설에 실패했습니다.")
                return

            QMessageBox.information(
                self,
                "계좌 개설 완료",
                f"새 계좌가 개설되었습니다.\n\n계좌번호: {account_no}",
            )
            self.accept()
        except Exception as e:
            print(e)
            return None

