# services/db_service.py (기존 클래스에 메서드만 추가)
import os
import psycopg2
import psycopg2.extras
import hashlib
import random
from decimal import Decimal

class DBService:
    def __init__(self,
                 host="localhost",
                 dbname="myhts",
                 user="myhts",
                 password="myhts_pw",
                 port=5432):
        self.conn = psycopg2.connect(
            host=host,
            dbname=dbname,
            user=user,
            password=password,
            port=port,
        )
        self.conn.autocommit = True

    # 이미 있는 회원가입
    def insert_user(self, email: str, password: str) -> bool:
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        with self.conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO users (email, pw_hash, created_at)
                    VALUES (%s, %s, now());
                    """,
                    (email, pw_hash),
                )
                return True
            except psycopg2.Error as e:
                print("insert_user error:", e)
                return False

    # 🆕 이메일로 user_id 조회
    def get_user_id_by_email(self, email: str) -> int | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            row = cur.fetchone()
            return row[0] if row else None

    # 🆕 계좌번호 생성 (간단 랜덤)
    def _generate_account_no(self) -> str:
        # 예: 100-1234-5678 형태
        while True:
            body = "".join(str(random.randint(0, 9)) for _ in range(8))
            acc = f"100-{body[:4]}-{body[4:]}"
            if not self._account_no_exists(acc):
                print("generate_account_no :", acc)
                return acc

    def _account_no_exists(self, account_no: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM accounts WHERE account_no=%s", (account_no,))
            return cur.fetchone() is not None

    # 🆕 계좌 개설
    def create_account(self, user_id: int, name: str = "") -> str | None:
        # ✅ 환경변수에서 기본 잔액 읽기 (없으면 10,000,000)
        default_balance = Decimal(os.getenv("INITIAL_CASH", "10000000"))

        account_no = self._generate_account_no()
        with self.conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO accounts (user_id, account_no, name, balance, created_at)
                    VALUES (%s, %s, %s, %s, now());
                    """,
                    (user_id, account_no, name, default_balance),
                )
                return account_no
            except psycopg2.Error as e:
                print("create_account error:", e)
                return None

    def close(self):
        self.conn.close()
