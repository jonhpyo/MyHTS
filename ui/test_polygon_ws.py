# test_polygon_ws.py
from __future__ import annotations
import os, sys, json, time
from typing import List
from websocket import WebSocketApp
from dotenv import load_dotenv

FUTURES_URL = "wss://socket.polygon.io/futures"
STOCKS_URL  = "wss://socket.polygon.io/stocks"

def run_ws_test(api_key: str, url: str, subscribe_topics: List[str], label="futures"):
    print(f"\n[TEST] {label} url={url} topics={subscribe_topics}")

    def on_open(ws):
        print("[WS OPEN]")
        ws.send(f"auth {api_key}")
        if subscribe_topics:
            ws.send("subscribe " + ",".join(subscribe_topics))

    def on_message(ws, msg):
        try:
            payload = json.loads(msg)
        except Exception:
            print("[WS MSG RAW]", msg)
            return

        events = payload if isinstance(payload, list) else [payload]
        for ev in events:
            ev_type = ev.get("ev") or ev.get("T") or ev.get("type")
            if ev_type in {"status", "error"}:
                print("[STATUS]", ev)  # 이유가 들어있음
                continue
            if ev_type == "Q":
                sym = ev.get("sym") or ev.get("pair") or ev.get("ticker")
                bp  = ev.get("bp") or ev.get("bidPrice")
                ap  = ev.get("ap") or ev.get("askPrice")
                bs  = ev.get("bs") or ev.get("bidSize")
                aS  = ev.get("as") or ev.get("askSize")
                print(f"[QUOTE] {sym} bid={bp}@{bs} ask={ap}@{aS}")
            else:
                # 다른 이벤트는 참고용 출력
                print("[EV]", ev_type, ev)

    def on_error(ws, err):
        print("[WS ERROR]", err)

    def on_close(ws, code, reason):
        print(f"[WS CLOSED] code={code} reason={reason}")

    ws = WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    # 10~15초 정도만 돌려보고 종료
    from threading import Thread
    t = Thread(target=lambda: ws.run_forever(ping_interval=15, ping_timeout=10), daemon=True)
    t.start()
    time.sleep(15)
    try:
        ws.close()
    except Exception:
        pass

def main():
    # load_dotenv()
    api_key = "Kx5SfDcfyiFEjv4ZiHLgqHzB1mtx8QiX"
    if not api_key:
        print("POLYGON_API_KEY not found in .env")
        sys.exit(1)

    # ★ 여기에 검증하고 싶은 '선물' 티커를 넣으세요.
    #   계정/문서에 따라 예: "@NQ", "CME:NQZ2025", "NQZ2025" 등
    FUTURE_TICKERS = ["@NQ"]

    # Futures: Quote 채널은 "Q.<symbol>"
    futures_topics = [f"Q.{sym.strip()}" for sym in FUTURE_TICKERS if sym.strip()]

    # 1) 선물 채널 테스트
    run_ws_test(api_key, FUTURES_URL, futures_topics, label="futures")

    # 2) (옵션) 주식 채널로 키 정상 여부 확인
    #    선물에서 바로 끊기면, 여기서 Q.AAPL이 정상 수신되는지를 봅니다.
    test_stocks = os.getenv("TEST_STOCKS", "AAPL")
    stock_topics = [f"Q.{s.strip()}" for s in test_stocks.split(",") if s.strip()]
    run_ws_test(api_key, STOCKS_URL, stock_topics, label="stocks (sanity check)")

if __name__ == "__main__":
    main()
