import requests

class OrderBookAPI:
    def __init__(self, base="http://127.0.0.1:9000"):
        self.base = base.rstrip("/")

    def get_depth(self, symbol):
        url = f"{self.base}/orderbook/merged"
        try:
            r = requests.get(url, params={"symbol": symbol})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print("[OrderBookAPI] get_depth error:", e)
            return {"bids": [], "asks": []}

