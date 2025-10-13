# HTS Mock Project (PyQt5 + PyQtGraph + Mock Broker Adapters)

## 설치
pip install -r requirements.txt

## 실행
- Qt Designer에서 만든 nasdaq_extended.ui를 같은 폴더에 둔 뒤:
python app.py

## 환경변수
- Windows(PyCharm) → Run/Debug Configuration의 Environment variables에 설정
DATA_SOURCE=ALPACA  # 또는 ALPACA
SYMBOL=QQQ    # KIS 예시 (Alpaca면 AAPL 등)

# KIS
KIS_BASE_URL=https://openapivts.koreainvestment.com:29443
KIS_APP_KEY="demo"
KIS_APP_SECRET="demo"
KIS_PAPER=1

# Alpaca
ALPACA_KEY="PK7VDBLGNZWB6W351ME3"
ALPACA_SECRET="CWIsbeLyjvQu3aFglp4YOO9iZjgjkmtNwCL1Svac"


## Kiwoom(OpenAPI+) 사용법
- Windows에서 영웅문/HTS 설치 및 로그인 필요
- `pip install pykiwoom`
- 사용: `from adapters.kiwoom import KiwoomSource as DataSource`
- 분봉 TR: OPT10080, 일봉 TR: OPT10081, 현재가정보: OPT10001
- 컬럼명은 KOA Studio/문서에서 확인 후 필요시 키 매핑 수정

# NASDAQ
NASDAQ_BASE_URL=https://api.polygon.io
NASDAQ_KEY=Kx5SfDcfyiFEjv4ZiHLgqHzB1mtx8QiX
