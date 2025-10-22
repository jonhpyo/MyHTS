try:
    from PyQt6 import QtWidgets
    from PyQt6.QtCore import Qt
    _QT6 = True
except Exception:
    from PyQt5 import QtWidgets
    from PyQt5.QtCore import Qt
    _QT6 = False

class LoginDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.resize(360, 160)

        self.edit_user = QtWidgets.QLineEdit(self); self.edit_user.setPlaceholderText("User ID (demo/paper)")
        self.edit_pass = QtWidgets.QLineEdit(self); self.edit_pass.setPlaceholderText("Password (1234)")
        self.edit_pass.setEchoMode(
            QtWidgets.QLineEdit.EchoMode.Password if _QT6 else QtWidgets.QLineEdit.Password
        )
        self.lbl_error = QtWidgets.QLabel(self); self.lbl_error.setStyleSheet("color:#e66;")

        btn_login  = QtWidgets.QPushButton("Login", self)
        btn_cancel = QtWidgets.QPushButton("Cancel", self)
        btn_login.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        form = QtWidgets.QFormLayout()
        form.addRow("ID", self.edit_user)
        form.addRow("Password", self.edit_pass)
        v = QtWidgets.QVBoxLayout(self); v.addLayout(form); v.addWidget(self.lbl_error)
        h = QtWidgets.QHBoxLayout(); h.addStretch(1); h.addWidget(btn_cancel); h.addWidget(btn_login); v.addLayout(h)

    def credentials(self):
        return self.edit_user.text().strip(), self.edit_pass.text()
