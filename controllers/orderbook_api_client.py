# controllers/orderbook_api_client.py
import requests


class OrderBookAPIClient:
    def __init__(self, api_url="http://127.0.0.1:9000"):
        self.api_url = api_url.rstrip("/")

    # ------------------------------------------------------
    # 1) Local DB 기반 (order table)
    # ------------------------------------------------------
    def get_local_depth(self, symbol):
        url = f"{self.api_url}/orderbook/local"
        try:
            r = requests.get(url, params={"symbol": symbol}, timeout=2)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print("[OrderBookAPI] get_local_depth error:", e)
            return {"bids": [], "asks": []}

    # ------------------------------------------------------
    # 2) Binance Real-Time Depth (가격만 실제로 사용)
    # ------------------------------------------------------
    def get_binance_depth(self, symbol):
        url = f"{self.api_url}/orderbook/binance"
        try:
            r = requests.get(url, params={"symbol": symbol}, timeout=2)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print("[OrderBookAPI] get_binance_depth error:", e)
            return {"bids": [], "asks": [], "mid": 0}

    # ------------------------------------------------------
    # 3) ★ 최종 병합본 (UI는 이것만 쓰면 됨)
    # ------------------------------------------------------
    def get_depth(self, symbol):
        """
        /orderbook/merged 호출
        Binance 가격 + Local qty/cnt 을 조합한 최종 데이터
        """
        url = f"{self.api_url}/orderbook/merged"
        try:
            r = requests.get(url, params={"symbol": symbol}, timeout=3)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print("[OrderBookAPI] get_depth error:", e)
            return {"bids": [], "asks": [], "mid": 0}
