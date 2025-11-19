import requests

class TradeControllerAPI:
    def __init__(self, engine_url="http://127.0.0.1:9000"):
        self.engine_url = engine_url.rstrip("/")

    def insert_trade(self, trade_dict):
        r = requests.post(f"{self.engine_url}/trades/insert", json=trade_dict)
        return r.json()

    def get_trades(self, user_id, limit=100):
        r = requests.get(f"{self.engine_url}/trades/my",
                         params={"user_id": user_id, "limit": limit})
        return r.json().get("trades", [])


