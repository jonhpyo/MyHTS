# controllers/auth_controller.py
import hashlib
from services.db_service import DBService


class AuthController:
    """로그인 / 로그아웃 / 현재 사용자 상태 관리"""

    def __init__(self, db: DBService | None = None):
        self.db = db or DBService()
        self.current_user: str | None = None  # 이메일

    def login(self, email: str, pw: str) -> bool:
        """users 테이블에서 비밀번호 검증 후 로그인"""
        pw_hash = hashlib.sha256(pw.encode()).hexdigest()

        with self.db.conn.cursor() as cur:
            cur.execute("SELECT id, pw_hash FROM users WHERE email=%s", (email,))
            row = cur.fetchone()

        if not row:
            print("[Auth] 존재하지 않는 사용자:", email)
            return False

        stored_hash = row[1]
        if stored_hash == pw_hash:
            self.current_user = email
            print(f"[Auth] 로그인 성공: {email}")
            return True

        print("[Auth] 비밀번호 불일치:", email)
        return False

    def logout(self) -> str | None:
        """로그아웃"""
        user = self.current_user
        self.current_user = None
        print(f"[Auth] 로그아웃: {user}")
        return user

    def is_logged_in(self) -> bool:
        return self.current_user is not None
