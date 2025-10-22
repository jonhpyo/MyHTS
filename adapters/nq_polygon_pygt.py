import sys
import time
import threading
import datetime as dt
from typing import Optional, List, Dict

import requests
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QMainWindow, QTableWidgetItem

API_KEY = "Kx5SfDcfyiFEjv4ZiHLgqHzB1mtx8QiX"  # ← Polygon API 키 입력
BASE = "https://api.polygon.io"

# ---------- Polygon REST helpers ----------

def _today_utc_str():
    return dt.datetime.utcnow().strftime("%Y-%m-%d")

def pick_nearest_nq_contract(api_key: str) -> Optional[str]:
    """
    NQ 선물(이-미니 나스닥100) 중 오늘 기준 가장 가까운 만기 티커를 고릅니다.
    Polygon v3 Reference Tickers 이용. (market=futures, search=NQ)
    """
    url = f"{BASE}/v3/reference/tickers"
    params = {
        "market": "futures",
        "search": "NQ",
        "active": "true",
        "limit": 200,
        "apiKey": api_key,
        "sort": "expiration_date",
        "order": "asc",
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    results = data.get("results", []) or []

    today = dt.date.today()
    # expiration_date 형식: '2025-12-19' 등
    candidates = []
    for it in results:
        sym = it.get("ticker")
        exp = it.get("expiration_date")
        root = it.get("root_ticker")  # 'NQ' 혹은 유사
        if not sym or not exp:
            continue
        if root and not root.startswith("NQ"):
            continue
        try:
            exp_d = dt.datetime.strptime(exp, "%Y-%m-%d").date()
        except Exception:
            continue
        candidates.append((exp_d, sym))

    if not candidates:
        return None

    # 오늘 이후 만기 중 가장 빠른 것 우선, 없으면 전체 중 가장 가까운 것
    future = [c for c in candidates if c[0] >= today]
    chosen = min(future, key=lambda x: x[0]) if future else min(candidates, key=lambda x: abs((x[0]-today).days))
    return chosen[1]


# def fetch_intraday_1min_tail(ticker: str, api_key: str, limit_last: int = 60) -> List[Dict]: