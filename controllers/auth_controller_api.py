# controllers/auth_controller.py
import hashlib
import requests
from services.db_service import DBService


class AuthControllerAPI:
    """로그인 / 로그아웃 / 현재 사용자 상태 관리"""

    def __init__(self, api_url = "http://127.0.0.1:8000/"):
        self.api_url = api_url
        self.access_token: str | None = None
        self.user_id: int | None = None
        self.current_user: str | None = None


    def login(self, email: str, pw: str) -> bool:
        """
        API 서버 /login 호출 → JWT 토큰 획득
        """
        url = f"{self.api_url}/login"
        payload = {
            "username": email,
            "password": pw
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        try:
            res = requests.post(url, data=payload, headers=headers)
        except Exception as e:
            print("[Auth] 서버 접속 오류:", e)
            return False

        if res.status_code != 200:
            print("[Auth] 로그인 실패:", res.text)
            return False

        data = res.json()
        token = data.get("access_token")
        if not token:
            print("[Auth] 로그인 실패: 토큰 없음")
            return False

        self.access_token = token

        # ----------- /me 호출해서 user_id 확인 -----------
        me = self._fetch_me()
        if not me:
            print("[Auth] /me 조회 실패")
            return False

        self.user_id = me.get("user_id")
        self.current_user = email
        print("[Auth] 로그인 성공 → email =", self.current_user, self.user_id)
        return True

    # --------------------------
    # /me 조회 (토큰 기반 인증 테스트)
    # --------------------------
    def _fetch_me(self) -> dict | None:
        if not self.access_token:
            return None

        try:
            res = requests.get(
                f"{self.api_url}/me",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            if res.status_code == 200:
                return res.json()
            return None
        except Exception:
            return None

    # --------------------------
    # 토큰 포함 API 요청 헬퍼
    # --------------------------
    def authorized_request(self, method: str, path: str, **kwargs):
        """
        공통된 Authorization 헤더를 자동으로 붙여주는 요청 메서드
        """
        if not self.access_token:
            raise RuntimeError("로그인 필요")

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"

        return requests.request(
            method=method,
            url=f"{self.api_url}{path}",
            headers=headers,
            **kwargs
        )

    def logout(self) -> str | None:
        """로그아웃"""
        user = self.current_user
        self.current_user = None
        print(f"[Auth] 로그아웃: {user}")
        return user

    def is_logged_in(self) -> bool:
        return self.current_user is not None
