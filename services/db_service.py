# services/db_service.py (기존 클래스에 메서드만 추가)
import os
import psycopg2
import psycopg2.extras
import hashlib
import random
from decimal import Decimal

from services.simaccount import SimAccount


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

    import psycopg2.extras

    def get_account_summary(self, account_id: int):
        """잔고 + 포지션 목록 반환"""
        summary = {"balance": 0.0, "positions": []}

        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # 현금 잔고
            cur.execute("SELECT balance FROM accounts WHERE id=%s;", (account_id,))
            row = cur.fetchone()
            summary["balance"] = float(row["balance"]) if row else 0.0

            # 보유 포지션
            cur.execute(
                """
                SELECT symbol, qty, avg_price, updated_at
                FROM positions
                WHERE account_id=%s
                ORDER BY symbol;
                """,
                (account_id,),
            )
            rows = cur.fetchall()

            positions: list[dict] = []
            for r in rows:
                positions.append(
                    {
                        "symbol": str(r["symbol"]),
                        "qty": float(r["qty"]),
                        "avg_price": float(r["avg_price"]),
                        "updated_at": r["updated_at"],
                    }
                )

            summary["positions"] = positions

        return summary

    def load_account_from_db(self, account_id: int):
        """
        DB 계좌 요약을 SimAccount에 로드하여 UI에 반영 가능한 형태로 만든다.
        """
        summary = self.get_account_summary(account_id)

        # SimAccount 초기화
        self.account = SimAccount
        self.account.cash = summary.get("balance", 0.0)

        # DB positions → SimAccount.positions
        for row in summary.get("positions", []):
            symbol = row["symbol"]
            qty = float(row["qty"])
            avg_price = float(row["avg_price"])

            pos = self.account._get_or_create_position(symbol)
            pos.position = qty
            pos.avg_price = avg_price

        # 마지막 가격 정보는 DB가 모르므로,
        # 마크투마켓은 md 핸들러에서 mid/fetchprice로 갱신하면 됨.

        return self.account

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

    def place_market_buy(self, user_id: int, account_id: int, symbol: str, qty: float, ioc: bool = True):
        """
        시장가 매수:
          - 주문 레코드(type='MKT') 생성
          - 최저가 SELL부터 체결
          - 잔액/주문 잔량/상태/체결 테이블 모두 갱신
          - ioc=True 이면 남은 수량은 즉시 취소(CANCELLED), False면 잔량 WORKING 으로 남김

        반환:
          {
            "order_id": int,
            "filled_qty": float,
            "avg_price": float | None,
            "spent": float,               # 총 체결대금
            "leftover": float,            # 남은 수량(IOC면 0으로 처분됨)
            "trades": [ { "price":p, "qty":q, "sell_order_id":sid }, ... ]
          }
        """
        conn = self.conn
        result = {
            "order_id": None,
            "filled_qty": 0.0,
            "avg_price": None,
            "spent": 0.0,
            "leftover": float(qty),
            "trades": [],
        }

        if qty <= 0:
            return result

        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 1) 시장가 주문 INSERT (price는 NULL/0, type='MKT')
                cur.execute(
                    """
                    INSERT INTO orders (user_id, account_id, symbol, side, price, quantity, remaining_qty, status, created_at)
                    VALUES (%s, %s, %s, 'BUY', NULL, %s, %s, 'WORKING', now())
                    RETURNING id;
                    """,
                    (user_id, account_id, symbol, qty, qty),
                )
                buy_order_id = cur.fetchone()["id"]
                result["order_id"] = buy_order_id

                remaining = float(qty)
                total_notional = 0.0
                total_filled = 0.0

                # 2) 체결 대상 SELL 주문 락 잡고 조회 (최저가 우선, 오래된 순)
                cur.execute(
                    """
                    SELECT id, account_id, price, remaining_qty
                    FROM orders
                    WHERE symbol = %s
                      AND side = 'SELL'
                      AND status IN ('WORKING','PARTIAL')
                    ORDER BY price ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED;
                    """,
                    (symbol,),
                )
                sell_rows = cur.fetchall()

                trades = []

                # 3) 매칭 루프
                for s in sell_rows:
                    if remaining <= 0:
                        break
                    sell_id = s["id"]
                    sell_acc = s["account_id"]
                    sell_px = float(s["price"])
                    sell_rem = float(s["remaining_qty"])

                    if sell_rem <= 0:
                        continue

                    fill_qty = min(remaining, sell_rem)
                    notional = sell_px * fill_qty

                    # 체결 기록
                    cur.execute(
                        """
                        INSERT INTO trades (buy_order_id, sell_order_id, symbol, price, quantity, trade_time)
                        VALUES (%s, %s, %s, %s, %s, now());
                        """,
                        (buy_order_id, sell_id, symbol, sell_px, fill_qty),
                    )

                    # 판매자 주문 잔량/상태
                    new_sell_rem = sell_rem - fill_qty
                    new_sell_status = "FILLED" if new_sell_rem <= 0 else "PARTIAL"
                    cur.execute(
                        """
                        UPDATE orders
                        SET remaining_qty = %s, status = %s
                        WHERE id = %s;
                        """,
                        (new_sell_rem, new_sell_status, sell_id),
                    )

                    # 계좌 잔액 갱신: BUY(-), SELL(+)
                    cur.execute(
                        "UPDATE accounts SET balance = balance - %s WHERE id = %s;",
                        (notional, account_id),
                    )
                    cur.execute(
                        "UPDATE accounts SET balance = balance + %s WHERE id = %s;",
                        (notional, sell_acc),
                    )

                    trades.append({"price": sell_px, "qty": fill_qty, "sell_order_id": sell_id})
                    remaining -= fill_qty
                    total_filled += fill_qty
                    total_notional += notional

                # 4) 시장가 주문 상태/잔량 정리
                if total_filled > 0:
                    avg_price = total_notional / total_filled
                else:
                    avg_price = None

                if remaining <= 0:
                    # 전량 체결
                    cur.execute(
                        "UPDATE orders SET remaining_qty=0, status='FILLED' WHERE id=%s;",
                        (buy_order_id,),
                    )
                else:
                    if ioc:
                        # 체결 안 된 잔량 즉시 취소 (IOC)
                        cur.execute(
                            "UPDATE orders SET remaining_qty=0, status='CANCELLED' WHERE id=%s;",
                            (buy_order_id,),
                        )
                    else:
                        # 잔량을 살아있는 'MKT'로 두고 싶다면 여기서 'WORKING' 유지
                        cur.execute(
                            "UPDATE orders SET remaining_qty=%s, status='PARTIAL' WHERE id=%s;",
                            (remaining, buy_order_id),
                        )

                result.update({
                    "filled_qty": total_filled,
                    "avg_price": avg_price,
                    "spent": total_notional,
                    "leftover": remaining if not ioc else 0.0,
                    "trades": trades,
                })

            conn.commit()
        except Exception as e:
            conn.rollback()
            print("[DBService] place_market_buy error:", e)

        return result

    # services/db_service.py
    import psycopg2
    import psycopg2.extras

    def place_market_sell(self, user_id: int, account_id: int, symbol: str, qty: float, ioc: bool = True):
        """
        시장가 매도:
          - SELL 시장가 주문(type='MKT') 생성
          - 최고가 BUY부터 체결
          - trades/주문잔량/주문상태/계좌잔액 모두 한 트랜잭션으로 처리
          - ioc=True면 남은 수량은 즉시 취소

        반환 예:
          {
            "order_id": int,
            "filled_qty": float,
            "avg_price": float|None,
            "received": float,      # 총 체결대금(매도자 수령액)
            "leftover": float,      # 남은 수량(IOC면 0)
            "trades": [ { "price":p, "qty":q, "buy_order_id": bid }, ... ]
          }
        """
        conn = self.conn
        result = {
            "order_id": None,
            "filled_qty": 0.0,
            "avg_price": None,
            "received": 0.0,
            "leftover": float(qty),
            "trades": [],
        }
        if qty <= 0:
            return result

        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 1) SELL 시장가 주문 생성
                cur.execute(
                    """
                    INSERT INTO orders (user_id, account_id, symbol, side, price, quantity, remaining_qty, status, created_at)
                    VALUES (%s, %s, %s, 'SELL', NULL, %s, %s, 'WORKING', now())
                    RETURNING id;
                    """,
                    (user_id, account_id, symbol, qty, qty),
                )
                sell_order_id = cur.fetchone()["id"]
                result["order_id"] = sell_order_id

                remaining = float(qty)
                total_notional = 0.0
                total_filled = 0.0

                # 2) 체결 대상: BUY 주문 (최고가 우선, 오래된 순)
                cur.execute(
                    """
                    SELECT id, account_id, price, remaining_qty
                    FROM orders
                    WHERE symbol = %s
                      AND side = 'BUY'
                      AND status IN ('WORKING','PARTIAL')
                    ORDER BY price DESC, created_at ASC
                    FOR UPDATE SKIP LOCKED;
                    """,
                    (symbol,),
                )
                buy_rows = cur.fetchall()

                trades = []

                # 3) 매칭 루프
                for b in buy_rows:
                    if remaining <= 0:
                        break
                    buy_id = b["id"]
                    buy_acc = b["account_id"]
                    buy_px = float(b["price"])
                    buy_rem = float(b["remaining_qty"])
                    if buy_rem <= 0:
                        continue

                    fill_qty = min(remaining, buy_rem)
                    notional = buy_px * fill_qty

                    # 체결 기록
                    cur.execute(
                        """
                        INSERT INTO trades (buy_order_id, sell_order_id, symbol, price, quantity, trade_time)
                        VALUES (%s, %s, %s, %s, %s, now());
                        """,
                        (buy_id, sell_order_id, symbol, buy_px, fill_qty),
                    )

                    # BUY 주문 잔량/상태
                    new_buy_rem = buy_rem - fill_qty
                    new_buy_status = "FILLED" if new_buy_rem <= 0 else "PARTIAL"
                    cur.execute(
                        "UPDATE orders SET remaining_qty=%s, status=%s WHERE id=%s;",
                        (new_buy_rem, new_buy_status, buy_id),
                    )

                    # 계좌 잔액: BUY(-), SELL(+)
                    cur.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s;", (notional, buy_acc))
                    cur.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s;", (notional, account_id))

                    trades.append({"price": buy_px, "qty": fill_qty, "buy_order_id": buy_id})
                    remaining -= fill_qty
                    total_filled += fill_qty
                    total_notional += notional

                # 4) SELL 시장가 주문 상태 정리
                avg_price = (total_notional / total_filled) if total_filled > 0 else None
                if remaining <= 0:
                    cur.execute("UPDATE orders SET remaining_qty=0, status='FILLED' WHERE id=%s;", (sell_order_id,))
                else:
                    if ioc:
                        cur.execute("UPDATE orders SET remaining_qty=0, status='CANCELLED' WHERE id=%s;",
                                    (sell_order_id,))
                    else:
                        cur.execute("UPDATE orders SET remaining_qty=%s, status='PARTIAL' WHERE id=%s;",
                                    (remaining, sell_order_id))

                result.update({
                    "filled_qty": total_filled,
                    "avg_price": avg_price,
                    "received": total_notional,
                    "leftover": remaining if not ioc else 0.0,
                    "trades": trades,
                })

            conn.commit()
        except Exception as e:
            conn.rollback()
            print("[DBService] place_market_sell error:", e)

        return result

    def update_position_on_trade(self, account_id: int, user_id: int, symbol: str, side: str, price: float, qty: float):
        """
        체결이 발생할 때 포지션을 갱신.
        side: 'BUY' → 보유수량 +, 평균단가 재계산
              'SELL' → 보유수량 -, 실현손익 계산 가능
        """
        conn = self.conn
        side = side.upper()
        try:
            with conn.cursor() as cur:
                # 기존 포지션 조회
                cur.execute(
                    "SELECT qty, avg_price FROM positions WHERE account_id=%s AND symbol=%s;",
                    (account_id, symbol),
                )
                row = cur.fetchone()

                if row:
                    old_qty, old_avg = float(row[0]), float(row[1])
                else:
                    old_qty, old_avg = 0.0, 0.0

                new_qty = old_qty
                new_avg = old_avg

                if side == "BUY":
                    total_cost = old_qty * old_avg + qty * price
                    new_qty = old_qty + qty
                    new_avg = total_cost / new_qty if new_qty > 0 else 0.0
                elif side == "SELL":
                    new_qty = old_qty - qty
                    if new_qty < 0:
                        new_qty = 0.0  # (공매도 지원하려면 이 조건 제거)
                    # 평균단가는 매도 시 유지

                if row:
                    if new_qty > 0:
                        cur.execute(
                            "UPDATE positions SET qty=%s, avg_price=%s, updated_at=now() WHERE account_id=%s AND symbol=%s;",
                            (new_qty, new_avg, account_id, symbol),
                        )
                    else:
                        cur.execute(
                            "DELETE FROM positions WHERE account_id=%s AND symbol=%s;",
                            (account_id, symbol),
                        )
                else:
                    cur.execute(
                        """
                        INSERT INTO positions (user_id, account_id, symbol, qty, avg_price)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (user_id, account_id, symbol, qty, price),
                    )

            conn.commit()
        except Exception as e:
            conn.rollback()
            print("[DBService] update_position_on_trade error:", e)

    def get_positions_by_account(self, account_id: int):
        """해당 계좌의 보유 포지션 목록 반환"""
        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT symbol, qty, avg_price, updated_at
                FROM positions
                WHERE account_id=%s
                ORDER BY symbol;
                """,
                (account_id,),
            )
            return cur.fetchall()

    def upsert_position(self, account_id: int, symbol: str, qty: float, avg_price: float):
        """
        positions 테이블에 (account_id, symbol)에 해당하는 포지션을
        qty / avg_price 기준으로 덮어쓴다.
        (SimAccount가 계산한 값을 그대로 저장하는 방식)
        """
        sql = """
        INSERT INTO positions (account_id, symbol, qty, avg_price, updated_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (account_id, symbol)
        DO UPDATE SET
            qty = EXCLUDED.qty,
            avg_price = EXCLUDED.avg_price,
            updated_at = NOW();
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (account_id, symbol, qty, avg_price))
        self.conn.commit()

    def close(self):
        self.conn.close()
