# controllers/account_controller_api.py
import requests


class AccountControllerAPI:
    """
    PyQt → FastAPI 계좌 관련 API 호출 컨트롤러
    """

    def __init__(self, base_url="http://127.0.0.1:9000"):
        self.base_url = base_url.rstrip("/")
        self.access_token = None  # AuthControllerAPI 에서 주입해야 함

    # ---------------------------------------------------
    # 내부: 인증 헤더
    # ---------------------------------------------------
    def _headers(self):
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    # ---------------------------------------------------
    # 1) 기본 계좌 가져오기
    # ---------------------------------------------------
    def get_primary_account_id(self, user_id: int):
        try:
            url = f"{self.base_url}/account/primary"
            res = requests.get(url, headers=self._headers(), timeout=3)

            if res.status_code == 401:
                print("[AccountAPI] get_primary_account_id: Unauthorized (token missing or expired)")
                return None

            if res.status_code != 200:
                print("[AccountAPI] get_primary_account_id error:", res.text)
                return None

            return res.json().get("account_id")

        except Exception as e:
            print("[AccountAPI] get_primary_account_id exception:", e)
            return None

    # ---------------------------------------------------
    # 2) 계좌 요약 정보 가져오기 (잔고 + 포지션)
    # ---------------------------------------------------
    def get_account_summary(self, account_id: int):
        try:
            url = f"{self.base_url}/account/summary"
            params = {"account_id": account_id}

            res = requests.get(url, params=params, headers=self._headers(), timeout=3)
            if res.status_code != 200:
                print("[AccountAPI] get_account_summary error:", res.text)
                return {"balance": 0, "positions": []}

            return res.json()
        except Exception as e:
            print("[AccountAPI] get_summary exception:", e)
            return {"balance": 0, "positions": []}

    # ---------------------------------------------------
    # 3) 모든 계좌 목록 가져오기
    # ---------------------------------------------------
    def get_accounts_by_user(self, user_id: int):
        try:
            url = f"{self.base_url}/account/list"
            res = requests.get(url, headers=self._headers(), timeout=3)
            if res.status_code != 200:
                print("[AccountAPI] get_accounts_by_user error:", res.text)
                return []
            return res.json()
        except Exception as e:
            print("[AccountAPI] get_accounts exception:", e)
            return []

    # ---------------------------------------------------
    # 4) 신규 계좌 개설
    # ---------------------------------------------------
    def open_account(self, user_id: int, account_no: str):
        try:
            url = f"{self.base_url}/account/open"
            body = {
                "user_id": user_id,
                "account_no": account_no,
            }

            res = requests.post(url, json=body, headers=self._headers(), timeout=5)
            if res.status_code != 200:
                print("[AccountAPI] open_account error:", res.text)
                return None

            return res.json().get("account_id")
        except Exception as e:
            print("[AccountAPI] open_account exception:", e)
            return None
