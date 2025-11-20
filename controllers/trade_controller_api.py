import requests

class TradeControllerAPI:
    def __init__(self, engine_url="http://127.0.0.1:9000"):
        self.engine_url = engine_url.rstrip("/")
        self.access_token = None   # AuthControllerAPI에서 주입해야 함

    # 내부용 헤더
    def _headers(self):
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    # -------------------------------------------------
    # 거래 삽입 (매칭엔진이 호출하는 경우)
    # -------------------------------------------------
    def insert_trade(self, trade_dict):
        r = requests.post(
            f"{self.engine_url}/trades/insert",
            json=trade_dict,
            headers=self._headers()
        )
        return r.json()

    # -------------------------------------------------
    # 나의 체결 조회 (/trades/my)
    # -------------------------------------------------
    def get_trades(self, limit=100):
        r = requests.get(
            f"{self.engine_url}/trades/my",
            params={"limit": limit},
            headers=self._headers()
        )

        if r.status_code != 200:
            print("[TradeAPI] get_trades error:", r.text)
            return []

        # 서버는 리스트 자체를 반환하므로 .get 사용 금지
        return r.json()
