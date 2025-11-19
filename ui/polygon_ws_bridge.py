import json, threading, time
from typing import Callable, List, Optional, Tuple, Any
from websocket import WebSocketApp

Depth = Tuple[float, int, int]

class PolygonWSBridge:
    def __init__(
        self,
        api_key: str,
        tickers: List[str],
        on_depth: Callable[[List[Depth], List[Depth], Optional[float]], None],
        url: str = "wss://socket.polygon.io/futures",
        auto_reconnect_sec: int = 5,
        on_status: Optional[Callable[[dict], None]] = None,
        on_closed: Optional[Callable[[Optional[int], Optional[str]], None]] = None,
    ):
        self.api_key = api_key
        self.tickers = tickers
        self.on_depth = on_depth
        self.url = url
        self.auto_reconnect_sec = auto_reconnect_sec
        self.on_status = on_status
        self.on_closed = on_closed

        self.ws: Optional[WebSocketApp] = None
        self._stop = False
        self._authed = False
        self._subscribed = False

    def _on_open(self, ws: WebSocketApp):
        print("[POLYGON OPEN] connected to", self.url)
        # ⚠️ 여기서는 아무 것도 보내지 않음 (connected 신호를 기다림)

    def _send_auth(self, ws: WebSocketApp):
        msg = {"action": "auth", "params": self.api_key}
        print("[POLYGON →] AUTH(JSON)")
        ws.send(json.dumps(msg))

    def _subscribe(self, ws: WebSocketApp):
        topics = ",".join([f"Q.{t}" for t in self.tickers])
        msg = {"action": "subscribe", "params": topics}
        print("[POLYGON →] SUBSCRIBE(JSON):", topics)
        ws.send(json.dumps(msg))

    def _on_message(self, ws: WebSocketApp, msg: str):
        try:
            payload = json.loads(msg)
        except Exception:
            print("[POLYGON RAW]", msg); return

        events = payload if isinstance(payload, list) else [payload]
        for ev in events:
            if not isinstance(ev, dict):
                continue
            ev_type = ev.get("ev") or ev.get("T") or ev.get("type")

            # ---- STATUS & ERROR ----
            if ev_type in {"status", "error"}:
                print("[POLYGON STATUS]", ev)
                if self.on_status:
                    try: self.on_status(ev)
                    except Exception: pass

                st = (ev.get("status") or "").lower()
                msg_txt = (ev.get("message") or "").lower()

                # 1) 서버가 connected 신호를 보냈을 때 → 이제 auth 전송
                if st == "connected" and not self._authed:
                    self._send_auth(ws)

                # 2) 인증 성공 확인
                if st in {"authenticated", "auth_success"}:
                    self._authed = True
                    # 인증 직후 구독
                    if not self._subscribed:
                        self._subscribe(ws)

                # 3) 구독 성공 확인
                if "subscribed to" in msg_txt:
                    self._subscribed = True

                # 권한/심볼 문제 로그
                if "not entitled" in msg_txt or "invalid" in msg_txt:
                    print("[POLYGON WARN] entitlement/symbol issue")

                return

            # ---- QUOTE ----
            if ev_type != "Q":
                # 다른 이벤트는 무시
                return

            bp = ev.get("bp") or ev.get("bidPrice")
            ap = ev.get("ap") or ev.get("askPrice")
            bs = ev.get("bs") or ev.get("bidSize")
            aS = ev.get("as") or ev.get("askSize")
            bids, asks = [], []
            if bp is not None and bs:
                bids.append((float(bp), int(bs), 1))
            if ap is not None and aS:
                asks.append((float(ap), int(aS), 1))
            if not bids and not asks:
                return
            mid = (bids[0][0] + asks[0][0]) / 2.0 if (bids and asks) else None
            self.on_depth(bids, asks, mid)

    def _on_error(self, ws: WebSocketApp, error: Any):
        print("[POLYGON ERROR]", error)

    def _on_close(self, ws: WebSocketApp, code: Optional[int], reason: Optional[str]):
        print(f"[POLYGON CLOSED] code={code} reason={reason}")
        if self.on_closed:
            try: self.on_closed(code, reason)
            except Exception: pass

    def _run_once(self):
        self.ws = WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        # 핑 유지 (타임아웃 방지)
        self.ws.run_forever(ping_interval=15, ping_timeout=10)

    def start(self):
        self._stop = False
        def loop():
            while not self._stop:
                self._authed = False
                self._subscribed = False
                try:
                    self._run_once()
                except Exception as e:
                    print("[POLYGON LOOP EXCEPTION]", e)
                if self._stop: break
                time.sleep(self.auto_reconnect_sec)
        threading.Thread(target=loop, daemon=True).start()

    def stop(self):
        self._stop = True
        try:
            if self.ws: self.ws.close()
        except Exception:
            pass
