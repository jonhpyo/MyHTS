import requests


class OrdersControllerAPI:
    def __init__(self, api_url="http://127.0.0.1:9000"):
        self.api_url = api_url.rstrip("/")
        self.access_token = None  # ★ 로그인 후 MainWindow에서 설정됨

    # ------------------------------------------------------
    # 내부 공용 함수 (헤더 자동 추가)
    # ------------------------------------------------------
    def _headers(self):
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    # ------------------------------------------------------
    # LIMIT ORDER
    # ------------------------------------------------------
    def place_limit(self, user_id, account_id, symbol, side, price, qty):
        url = f"{self.api_url}/orders/limit"

        payload = {
            "user_id": user_id,
            "account_id": account_id,
            "symbol": symbol,
            "side": side,
            "price": price,
            "qty": qty,
        }

        try:
            res = requests.post(url, json=payload, headers=self._headers())
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print("[OrdersAPI] place_limit error:", e, res.text if res else "")
            return None

    # ------------------------------------------------------
    # MARKET ORDER
    # ------------------------------------------------------
    def place_market(self, user_id, account_id, symbol, side, qty):
        url = f"{self.api_url}/orders/market"

        payload = {
            "user_id": user_id,
            "account_id": account_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
        }

        try:
            res = requests.post(url, json=payload, headers=self._headers())
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print("[OrdersAPI] place_market error:", e)
            return None

    # ------------------------------------------------------
    # CANCEL
    # ------------------------------------------------------
    def cancel_orders(self, order_ids):
        url = f"{self.api_url}/orders/cancel"
        payload = {"order_ids": order_ids}

        try:
            res = requests.post(url, json=payload, headers=self._headers())
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print("[OrdersAPI] cancel_orders error:", e)
            return None

    # ------------------------------------------------------
    # WORKING ORDERS 조회
    # ------------------------------------------------------
    def get_user_working_orders(self, user_id, limit=100):
        url = f"{self.api_url}/orders/working?user_id={user_id}&limit={limit}"

        try:
            res = requests.get(url, headers=self._headers())  # ★ 인증 추가
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print("[OrdersAPI] get_user_working_orders error:", e)
            return []
