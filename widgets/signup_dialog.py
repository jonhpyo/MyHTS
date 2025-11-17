import requests
from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox
from services.db_service import DBService

class SignupDialog(QDialog):
    def __init__(self, db: DBService, parent=None):
        super().__init__(parent)
        self.db = db

        self.setWindowTitle("회원가입")

        layout = QFormLayout(self)

        self.edit_email = QLineEdit()
        self.edit_password = QLineEdit()
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)

        layout.addRow("이메일", self.edit_email)
        layout.addRow("비밀번호", self.edit_password)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.on_accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    def on_accept(self):
        email = self.edit_email.text().strip()
        pw = self.edit_password.text().strip()

        if not email or not pw:
            QMessageBox.warning(self, "입력 오류", "이메일과 비밀번호를 모두 입력하세요.")
            return

        payload = {
            "email": email,
            "password": pw,
        }

        try:
            resp = requests.post(
                "http://localhost:8000/signup",
                json=payload,
                timeout=5,
            )
        except Exception as e:
            QMessageBox.critical(self, "서버 오류", f"/signup 서버 호출 실패:\n{e}")
            return

        if resp.status_code == 200 or resp.status_code == 201:
            data_json = resp.json()
            email = data_json.get("email")
            QMessageBox.information(self, "완료", "회원가입이 완료되었습니다.")
            self.accept()
        else:
            try:
                detail = resp.json().get("detail")
            except Exception:
                detail = None

            if detail:
                QMessageBox.warning(self, "오류", "이미 등록된 이메일이거나 DB 오류가 발생했습니다.")
            else:
                QMessageBox.warning(
                    self,
                    "오류",
                    f"회원가입 실패 (HTTP {resp.status_code})",
                )
