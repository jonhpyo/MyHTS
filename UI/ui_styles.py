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
def apply_header_style(table_widget, stylesheet: str):
    table_widget.horizontalHeader().setStyleSheet(stylesheet)
