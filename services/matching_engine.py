# services/matching_engine.py
import psycopg2.extras



class MatchingEngine:
    def __init__(self, db: "DBService"):
        self.db = db

    import psycopg2
    import psycopg2.extras

    def match_symbol(self, symbol: str):
        """
        symbol에 대한 WORKING 주문들을 가져와
        BUY.price >= SELL.price 인 만큼 체결 생성
        """
        conn = self.db.conn
        trades = []  # 예외 발생 시에도 참조 가능하도록 미리 선언

        try:
            from psycopg2.extras import RealDictCursor

            # 1) 매칭 대상 주문 조회 (잔량 > 0 인 주문만)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM orders
                    WHERE UPPER(symbol) = UPPER(%s)
                      AND status IN ('WORKING','PARTIAL')
                      AND remaining_qty > 0
                    ORDER BY
                        CASE WHEN side='BUY' THEN -price ELSE price END,
                        created_at ASC;
                    """,
                    (symbol,),
                )
                orders = cur.fetchall()

            buys = [o for o in orders if o["side"].upper() == "BUY"]
            sells = [o for o in orders if o["side"].upper() == "SELL"]

            if not buys or not sells:
                # 한쪽이라도 없으면 체결 없음
                return

            # 2) 가격 매칭: 최고 매수 vs 최저 매도
            while buys and sells:
                buy = buys[0]
                sell = sells[0]

                buy_price = float(buy["price"])
                sell_price = float(sell["price"])

                # 가격 교차 조건: 최고 매수 < 최저 매도 이면 더 이상 체결 불가
                if buy_price < sell_price:
                    break

                buy_rem = float(buy["remaining_qty"])
                sell_rem = float(sell["remaining_qty"])

                # 혹시라도 0 이하 잔량이 섞여 있으면 해당 주문 제거하고 진행
                if buy_rem <= 1e-9:
                    buys.pop(0)
                    continue
                if sell_rem <= 1e-9:
                    sells.pop(0)
                    continue

                qty = min(buy_rem, sell_rem)
                if qty <= 1e-9:
                    # 실질적인 체결량이 없으면 루프 종료
                    break

                # 체결 가격(간단히 양쪽 가격 평균으로)
                price = (buy_price + sell_price) / 2.0

                # 메모리 상 잔량 업데이트
                buy_rem -= qty
                sell_rem -= qty
                buy["remaining_qty"] = buy_rem
                sell["remaining_qty"] = sell_rem

                trades.append((buy, sell, price, qty))

                # 잔량이 거의 0 이하면 FILLED 로 보고 리스트에서 제거
                if buy_rem <= 1e-9:
                    buys.pop(0)
                if sell_rem <= 1e-9:
                    sells.pop(0)

            # 3) DB 반영
            if not trades:
                # 실제 체결 없으면 DB 안 건드림
                return

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
                        rem = float(o["remaining_qty"])
                        # 소수점 오차 보정
                        if rem < 1e-9:
                            rem = 0.0
                        status = "FILLED" if rem <= 0 else "PARTIAL"

                        cur.execute(
                            """
                            UPDATE orders
                            SET remaining_qty = %s,
                                status = %s
                            WHERE id = %s;
                            """,
                            (rem, status, o["id"]),
                        )

                    # 🔁 계좌 잔고 갱신
                    notional = float(price) * float(qty)
                    #   - BUY: balance -= notional
                    #   - SELL: balance += notional
                    cur.execute(
                        "UPDATE accounts SET balance = balance - %s WHERE id = %s;",
                        (notional, buy["account_id"]),
                    )
                    cur.execute(
                        "UPDATE accounts SET balance = balance + %s WHERE id = %s;",
                        (notional, sell["account_id"]),
                    )

            conn.commit()
            print(f"[MatchingEngine] symbol={symbol} trades={len(trades)} created")

        except Exception as e:
            conn.rollback()
            print(f"[MatchingEngine] symbol={symbol} error:", e)

