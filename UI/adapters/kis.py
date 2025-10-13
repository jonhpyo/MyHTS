# adapters/kis.py
import os, time, requests
from typing import List, Tuple
from .base import MarketDataSource, Bar

KIS_BASE_URL = os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")
APP_KEY = os.getenv("KIS_APP_KEY", "")
APP_SECRET = os.getenv("KIS_APP_SECRET", "")
PAPER = os.getenv("KIS_PAPER", "1") == "1"

class KISSource(MarketDataSource):
    def __init__(self):
        self._token = self._issue_token()
    def _issue_token(self) -> str:
        url = f"{KIS_BASE_URL}/oauth2/tokenP" if PAPER else f"{KIS_BASE_URL}/oauth2/token"
        r = requests.post(url, json={"grant_type":"client_credentials","appkey":APP_KEY,"appsecret":APP_SECRET}, timeout=7)
        r.raise_for_status()
        return r.json()["access_token"]
    def _headers(self, tr_id: str):
        return {"authorization": f"Bearer {self._token}","appkey": APP_KEY,"appsecret": APP_SECRET,"tr_id": tr_id,"custtype": "P" if PAPER else "U"}
    def get_recent_bars(self, symbol: str, timeframe: str, limit: int) -> List[Bar]:
        tr_id = "FHKST03010200"  # 실제 문서 기준으로 교체 필요
        url = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        params = {"fid_cond_mrkt_div_code":"J","fid_input_iscd":symbol,"fid_period_div_code":"M","fid_org_adj_prc":"0","fid_input_hour_1":timeframe}
        r = requests.get(url, headers=self._headers(tr_id), params=params, timeout=7)
        r.raise_for_status()
        output = r.json().get("output", [])
        bars: List[Bar] = []
        for row in output[-limit:]:
            ymd_hms = row.get("stck_cntg_hour") or row.get("cntg_dt")
            try:
                ts = int(time.mktime(time.strptime(ymd_hms, "%Y%m%d%H%M%S"))) if ymd_hms else int(time.time())
            except Exception:
                ts = int(time.time())
            o = float(row.get("stck_oprc", 0)); h = float(row.get("stck_hgpr", 0))
            l = float(row.get("stck_lwpr", 0)); c = float(row.get("stck_prpr", 0)); v = float(row.get("acml_vol", 0))
            bars.append(Bar(ts=ts, o=o, h=h, l=l, c=c, v=v))
        return bars
    def get_last_trade(self, symbol: str) -> Tuple[int, float, int]:
        tr_id = "FHKST01010100"  # 실제 문서 기준으로 교체 필요
        url = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
        r = requests.get(url, headers=self._headers(tr_id), params={"fid_cond_mrkt_div_code":"J","fid_input_iscd":symbol}, timeout=7)
        r.raise_for_status()
        d = r.json().get("output", {})
        price = float(d.get("stck_prpr", 0.0)); size = int(d.get("cntg_vol", "0") or 0)
        ts = int(time.time())
        return (ts, price, size)
