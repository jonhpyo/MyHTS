# test_alpaca_auth.py
import os, requests
from dotenv import load_dotenv
load_dotenv()  # .env 사용 중이면 필요

KEY = (os.getenv("APCA_API_KEY_ID") or "").strip()
SEC = (os.getenv("APCA_API_SECRET_KEY") or "").strip()

print("KEY set:", bool(KEY), "len:", len(KEY))
print("SEC set:", bool(SEC), "len:", len(SEC))

headers = {
    "APCA-API-KEY-ID": KEY,
    "APCA-API-SECRET-KEY": SEC,
}

# 1) Market Data v2 (QQQ 1분봉 1개) - 무료는 feed=iex 권장
params = {
    "timeframe": "1Min",
    "start": "2025-10-08T00:00:00Z",
    "end":   "2025-10-09T23:59:59Z",
    "limit": 300,
    "feed": "iex",
    "adjustment": "raw"
}

r = requests.get("https://data.alpaca.markets/v2/stocks/QQQ/bars",
                 headers=headers, params=params, timeout=10)
print("DATA /bars status:", r.status_code, r.text[:200])

# 2) 최신 1개 바(멀티 엔드포인트) - symbols=QQQ
r2 = requests.get("https://data.alpaca.markets/v2/stocks/bars/latest",
                  headers=headers, params={"symbols": "QQQ", "feed": "iex"}, timeout=10)
print("DATA /bars/latest status:", r2.status_code, r2.text[:200])

# 3) (선택) 트레이딩 API로 계정 확인 - 키가 완전 무효인지 판별용
r3 = requests.get("https://paper-api.alpaca.markets/v2/account",
                  headers=headers, timeout=10)
print("PAPER /account status:", r3.status_code, r3.text[:200])
