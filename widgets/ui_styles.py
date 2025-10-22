# ui_styles.py
BLUE_HEADER = (
    "QHeaderView::section { "
    "background-color: #003366; "
    "color: white; "
    "font-weight: bold; "
    "font-size: 10pt; "
    "padding: 4px; "
    "border: 1px solid #222222; "
    "}"
)
DARK_HEADER = (
    "QHeaderView::section { "
    "background-color: #333333; "
    "color: white; font-weight: bold; padding: 3px; "
    "border: 1px solid #222222; }"
)

try:
    from PyQt6 import QtWidgets, QtGui, QtCore
    from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
    QtAlignCenter  = QtCore.Qt.AlignmentFlag.AlignCenter
    QtAlignRight   = QtCore.Qt.AlignmentFlag.AlignRight
    QtAlignVCenter = QtCore.Qt.AlignmentFlag.AlignVCenter
except Exception:
    from PyQt5 import QtWidgets, QtGui, QtCore
    from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem
    QtAlignCenter  = QtCore.Qt.AlignCenter
    QtAlignRight   = QtCore.Qt.AlignRight
    QtAlignVCenter = QtCore.Qt.AlignVCenter

def apply_header_style(table_widget, stylesheet: str):
    table_widget.horizontalHeader().setStyleSheet(stylesheet)
