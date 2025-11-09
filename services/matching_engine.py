# services/matching_engine.py
import psycopg2.extras
from services.db_service import DBService



class MatchingEngine:
    def __init__(self, db: "DBService"):
        self.db = db

    def match_symbol(self, symbol: str):
        try:
            """
            symbol에 대한 WORKING 주문들을 가져와
            BUY.price >= SELL.price 인 만큼 체결 생성
            """
            conn = self.db.conn

            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 1) 매칭 대상 주문 조회 (락을 걸고 처리하고 싶으면 FOR UPDATE 추가)
                cur.execute(
                    """
                    SELECT *
                    FROM orders
                    WHERE symbol = %s
                      AND status IN ('WORKING','PARTIAL')
                    ORDER BY
                        CASE WHEN side='BUY' THEN -price ELSE price END,
                        created_at ASC;
                    """,
                    (symbol,),
                )
                orders = cur.fetchall()

            buys  = [o for o in orders if o["side"] == "BUY"]
            sells = [o for o in orders if o["side"] == "SELL"]

            if not buys or not sells:
                return  # 매칭 없음

            trades = []

            # 2) 가격 매칭: 최고 매수 vs 최저 매도
            while buys and sells and buys[0]["price"] >= sells[0]["price"]:
                buy = buys[0]
                sell = sells[0]

                qty = min(buy["remaining_qty"], sell["remaining_qty"])
                # 가격은 간단히 평균/또는 먼저 온 주문 가격 등 규칙 선택
                price = float(buy["price"] + sell["price"]) / 2.0

                trades.append((buy, sell, price, qty))

                buy["remaining_qty"]  -= qty
                sell["remaining_qty"] -= qty

                if buy["remaining_qty"] <= 0:
                    buys.pop(0)
                if sell["remaining_qty"] <= 0:
                    sells.pop(0)

            # 3) DB 반영
            with conn.cursor() as cur:
                for buy, sell, price, qty in trades:
                    # 체결 기록
                    cur.execute(
                        """
                        INSERT INTO trades (buy_order_id, sell_order_id, symbol, price, quantity, trade_time)
                        VALUES (%s, %s, %s, %s, %s, now());
                        """,
                        (buy["id"], sell["id"], symbol, price, qty),
                    )

                    # 주문 잔량/상태 업데이트
                    for o in (buy, sell):
                        status = (
                            "FILLED" if o["remaining_qty"] <= 0
                            else "PARTIAL"
                        )
                        cur.execute(
                            """
                            UPDATE orders
                            SET remaining_qty = %s,
                                status = %s
                            WHERE id = %s;
                            """,
                            (o["remaining_qty"], status, o["id"]),
                        )

                    # 🔁 계좌 잔고 갱신 (간단 버전)
                    #   - BUY: balance -= price * qty
                    #   - SELL: balance += price * qty
                    cur.execute("UPDATE accounts SET balance = balance - %s * %s WHERE id = %s;",
                                (price, qty, buy["account_id"]))
                    cur.execute("UPDATE accounts SET balance = balance + %s * %s WHERE id = %s;",
                                (price, qty, sell["account_id"]))

            conn.commit()
            print(f"[MatchingEngine] symbol={symbol} trades={len(trades)} created")
        except:
            print(f"[MatchingEngine] symbol={symbol} trades={len(trades)} failed")
