# controllers/orderbook_controller_api.py
import requests


class OrderBookControllerAPI:
    """
    FastAPI /orderbook 엔드포인트에서 오더북 데이터를 가져오는 API 클라이언트
    """

    def __init__(self, api_url="http://127.0.0.1:9000"):
        self.api_url = api_url.rstrip("/")

    def get_depth(self, symbol: str):
        url = f"{self.api_url}/orderbook"
        params = {"symbol": symbol}

        try:
            r = requests.get(url, params=params, timeout=2)
            r.raise_for_status()
            return r.json()  # {bids: [...], asks: [...]}

        except Exception as e:
            print("[OrderBookControllerAPI] error:", e)
            return {"bids": [], "asks": []}
