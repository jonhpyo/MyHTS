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
        """
        trades 테이블 기준으로 특정 사용자의 체결내역 조회
        - BUY 또는 SELL 주문 중 어느 한쪽이라도 user_id가 일치하면 포함
        - UI용 컬럼: account_no, symbol, side, price, quantity, trade_time, remark
        """
        from psycopg2.extras import DictCursor

        with self.conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                SELECT 
                    a.account_no AS account_no,
                    t.symbol      AS symbol,
                    CASE
                        WHEN ob.user_id = %(user_id)s THEN 'BUY'
                        WHEN os.user_id = %(user_id)s THEN 'SELL'
                        ELSE 'N/A'
                    END AS side,
                    t.price       AS price,
                    t.quantity    AS quantity,
                    t.trade_time  AS trade_time,
                    ''::text      AS remark
                FROM trades t
                JOIN orders ob ON t.buy_order_id  = ob.id
                JOIN orders os ON t.sell_order_id = os.id
                JOIN accounts a ON (
                    (ob.user_id = %(user_id)s AND ob.account_id = a.id)
                    OR (os.user_id = %(user_id)s AND os.account_id = a.id)
                )
                WHERE ob.user_id = %(user_id)s OR os.user_id = %(user_id)s
                ORDER BY t.trade_time DESC
                LIMIT %(limit)s;
                """,
                {"user_id": user_id, "limit": limit},
            )
            rows = cur.fetchall()
            print(f"[DBService] get_trades_by_user({user_id}) -> {len(rows)} rows")
            return rows

    def insert_dummy_trade(
            self,
            user_id: int,
            account_id: int,
            symbol: str = "SOLUSDT",
            price: float | None = None,
            qty: float = 1.0,
    ) -> int | None:
        """
        현재 스키마 기준 더미 체결 1건 생성:

        1) orders 테이블에 BUY 주문 1개, SELL 주문 1개를 FILLED 상태로 INSERT
        2) trades 테이블에 (buy_order_id, sell_order_id, symbol, price, quantity, trade_time) INSERT

        - user_id, account_id : 둘 다 같은 사람/계좌로 self-trade 형태 (테스트용)
        - symbol, price, qty : 필요하면 호출할 때 override
        """

        side_buy = "BUY"
        side_sell = "SELL"

        # 가격 안 주면 대충 랜덤 생성
        if price is None:
            base = 100.0
            price = round(base + random.uniform(-5, 5), 2)

        qty = float(qty)

        try:
            with self.conn.cursor() as cur:
                # 1) BUY 주문 생성 (이미 전부 체결된 주문이라고 가정: remaining_qty=0, status='FILLED')
                cur.execute(
                    """
                    INSERT INTO orders
                        (user_id, account_id, symbol, side, price, quantity, remaining_qty, status, created_at)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, 0, 'FILLED', now())
                    RETURNING id;
                    """,
                    (user_id, account_id, symbol, side_buy, price, qty),
                )
                buy_order_id = cur.fetchone()[0]

                # 2) SELL 주문 생성 (마찬가지로 전부 체결된 주문)
                cur.execute(
                    """
                    INSERT INTO orders
                        (user_id, account_id, symbol, side, price, quantity, remaining_qty, status, created_at)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, 0, 'FILLED', now())
                    RETURNING id;
                    """,
                    (user_id, account_id, symbol, side_sell, price, qty),
                )
                sell_order_id = cur.fetchone()[0]

                # 3) trades 테이블에 체결 생성
                cur.execute(
                    """
                    INSERT INTO trades
                        (buy_order_id, sell_order_id, symbol, price, quantity, trade_time)
                    VALUES
                        (%s, %s, %s, %s, %s, now())
                    RETURNING id;
                    """,
                    (buy_order_id, sell_order_id, symbol, price, qty),
                )
                trade_id = cur.fetchone()[0]

            self.conn.commit()
            print("[DBService] insert_dummy_trade trade_id =", trade_id,
                  "buy_order_id =", buy_order_id, "sell_order_id =", sell_order_id)
            return trade_id

        except psycopg2.Error as e:
            self.conn.rollback()
            print("[DBService] insert_dummy_trade error:", e)
            return None



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

    def cancel_orders(self, order_ids: list[int]) -> int:
        """
        주문 ID 목록을 받아서 WORKING / PARTIAL 상태인 주문을 취소 상태로 변경.
        remaining_qty 는 0 으로 만든다.
        반환값: 실제로 취소된 건수
        """
        if not order_ids:
            return 0

        with self.conn.cursor() as cur:
            try:
                # psycopg2 가 list 를 자동으로 배열로 변환해줘서 ANY(%s) 사용 가능
                cur.execute(
                    """
                    UPDATE orders
                    SET status = 'CANCELLED',
                        remaining_qty = 0
                    WHERE id = ANY(%s)
                      AND status IN ('WORKING','PARTIAL');
                    """,
                    (order_ids,),
                )
                updated = cur.rowcount
                self.conn.commit()
                print(f"[DBService] cancel_orders ids={order_ids} -> {updated}행 취소")
                return updated
            except Exception as e:
                self.conn.rollback()
                print("[DBService] cancel_orders error:", e)
                return 0

    def get_working_orders_by_user(self, user_id: int, limit: int = 100):
        """해당 유저의 미체결 주문 목록 반환"""
        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT id, symbol, side, price, quantity, remaining_qty, created_at
                FROM orders
                WHERE user_id = %s AND status IN ('WORKING','PARTIAL')
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (user_id, limit),
            )
            return cur.fetchall()

    def get_local_orderbook(self, symbol: str):
        """
        로컬 거래소 기준 오더북 집계 (price별 잔량/건수)
        반환 예:
          {
            "bids": { 19999.0: {"qty": 5, "cnt": 2}, ... },
            "asks": { 20001.0: {"qty": 3, "cnt": 1}, ... },
          }
        """
        from psycopg2.extras import DictCursor
        data = {"bids": {}, "asks": {}}
        with self.conn.cursor(cursor_factory=DictCursor) as cur:
            # print("[DBService] get_local_orderbook symbol:", symbol)
            cur.execute(
                """
                SELECT side, price,
                       SUM(remaining_qty) AS qty,
                       COUNT(*)           AS cnt
                FROM orders
                WHERE symbol = %s
                  AND status IN ('WORKING','PARTIAL')
                GROUP BY side, price;
                """,
                (symbol,),
            )
            for row in cur.fetchall():
                side = row["side"].upper()
                price = float(row["price"])
                qty = float(row["qty"])
                cnt = int(row["cnt"])
                bucket = data["bids"] if side == "BUY" else data["asks"]
                bucket[price] = {"qty": qty, "cnt": cnt}
        return data

    def close(self):
        self.conn.close()
