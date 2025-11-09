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

    def get_account_balance(self, account_no: str) -> Decimal | None:
        """특정 계좌번호의 현재 잔액 조회"""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT balance FROM accounts WHERE account_no=%s",
                (account_no,),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def get_primary_account_id(self, user_id: int) -> int | None:
        """해당 유저의 기본 계좌 하나(id)만 가져오기 (가장 먼저 생성된 계좌 기준)"""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM accounts WHERE user_id=%s ORDER BY id LIMIT 1;",
                (user_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def get_accounts_by_user_id(self, user_id: int):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT account_no, name, balance FROM accounts WHERE user_id=%s ORDER BY id",
                (user_id,),
            )
            return cur.fetchall()

    def insert_trade(self, user_id: int, account_id: int, symbol: str,
                     side: str, price: float, qty: float,
                     order_id: str = None, exchange: str = None,
                     remark: str = None):
        with self.conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO trades (user_id, account_id, symbol, side,
                                        price, quantity, trade_time, order_id, exchange, remark)
                    VALUES (%s, %s, %s, %s, %s, %s, now(), %s, %s, %s);
                    """,
                    (user_id, account_id, symbol, side, price, qty, order_id, exchange, remark),
                )
                return True
            except psycopg2.Error as e:
                print("insert_trade error:", e)
                return False

    def get_trades_by_user(self, user_id: int, limit: int = 100):
        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    a.account_no   AS account_no,
                    t.symbol       AS symbol,
                    t.side         AS side,
                    t.price        AS price,
                    t.quantity     AS quantity,
                    t.trade_time   AS trade_time,
                    COALESCE(t.remark, '') AS remark
                FROM trades t
                JOIN accounts a ON t.account_id = a.id
                WHERE t.user_id = %s
                ORDER BY t.trade_time DESC
                LIMIT %s;
                """,
                (user_id, limit),
            )
            return cur.fetchall()

    def insert_dummy_trade(self, user_id: int, account_id: int) -> None:
        """테스트용 더미 체결 1건 삽입"""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trades
                    (user_id, account_id, symbol, side, price, quantity, trade_time, exchange, remark)
                VALUES
                    (%s, %s, 'SOLUSDT', 'BUY', 123.45, 1.23, now(), 'BINANCE', 'dummy from UI');
                """,
                (user_id, account_id),
            )

    def update_balance(self, account_id: int, delta: float):
        """거래 후 잔액 반영 (BUY는 -, SELL은 +)"""
        with self.conn.cursor() as cur:
            cur.execute("UPDATE accounts SET balance = balance + %s WHERE id=%s;", (delta, account_id))

    # ------------------------
    # orders (미체결 포함 주문)
    # ------------------------
    def insert_order(
        self,
        user_id: int,
        account_id: int,
        symbol: str,
        side: str,
        price: float,
        qty: float,
        remaining_qty: float | None = None,
        status: str = "WORKING",
    ) -> int | None:
        """지정가 주문 등 신규 주문을 DB에 저장하고 order_id 반환"""
        if remaining_qty is None:
            remaining_qty = qty

        with self.conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO orders
                        (user_id, account_id, symbol, side,
                         price, quantity, remaining_qty, status, created_at, updated_at)
                    VALUES
                        (%s, %s, %s, %s,
                         %s, %s, %s, %s, now(), now())
                    RETURNING id;
                    """,
                    (user_id, account_id, symbol, side, price, qty, remaining_qty, status),
                )
                order_id = cur.fetchone()[0]
                print("[DBService] insert_order id =", order_id)
                return order_id
            except psycopg2.Error as e:
                print("insert_order error:", e)
                return None

    def update_order_remaining(
        self,
        order_id: int,
        remaining_qty: float,
        status: str | None = None,
    ):
        """체결 진행에 따라 남은 수량 및 상태 업데이트"""
        with self.conn.cursor() as cur:
            if status is None:
                cur.execute(
                    """
                    UPDATE orders
                    SET remaining_qty = %s,
                        updated_at = now()
                    WHERE id = %s;
                    """,
                    (remaining_qty, order_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE orders
                    SET remaining_qty = %s,
                        status = %s,
                        updated_at = now()
                    WHERE id = %s;
                    """,
                    (remaining_qty, status, order_id),
                )


    def close(self):
        self.conn.close()
