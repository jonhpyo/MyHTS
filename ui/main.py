import sys, os
from dotenv import load_dotenv
from ib_insync import util
util.useQt()

try:
    from PyQt6 import QtWidgets
except Exception:
    from PyQt5 import QtWidgets

from ui.main_window import NasdaqWindow
import yfinance as yf

load_dotenv()
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

def get_last_close(symbol="NQ=F"):
    data = yf.download(symbol, period="2d", interval="1d",
                       progress=False, auto_adjust=False)  # 경고1 해결
    # 경고2: 단일 원소는 item()으로 꺼내기
    return float(data["Close"].iloc[-1].item())

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    use_mock = bool(os.getenv("USE_MOCK_DATA"))
    base = get_last_close("NQ=F")
    win = NasdaqWindow(use_mock=use_mock, base_price=base)
    win.show()
    sys.exit(app.exec())
