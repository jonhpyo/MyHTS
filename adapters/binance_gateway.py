# adapters/binance_gateway.py
import json
import threading
import traceback
from typing import Optional, Callable, List, Tuple

try:
    import websocket  # pip install websocket-client
except Exception as e:
    raise RuntimeError("websocket-client가 필요합니다: pip install websocket-client") from e


class BinanceGateway:
    """
    Binance 현물 WebSocket depth 스트림 구독.
    - symbol: 예) 'btcusdt', 'ethusdt' (소문자)
    - rows: 5, 10, 20 등 (Binance depth@<levels>)
    - interval: 100ms 또는 1000ms
    on_update(bids, asks) 콜백으로 [(price, size, level_index), ...] 전달
    """
    def __init__(self, symbol: str = "btcusdt", rows: int = 10, interval_ms: int = 100):
        self.symbol = symbol.lower()
        self.rows = int(rows)
        self.interval_ms = int(interval_ms)
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._on_update: Optional[Callable[[list, list], None]] = None
        self._closed = threading.Event()

    def connect(self, on_update: Callable[[list, list], None]):
        self._on_update = on_update
        stream = f"{self.symbol}@depth{self.rows}@{self.interval_ms}ms"
        url = f"wss://stream.binance.com:9443/ws/{stream}"

        def on_msg(_ws, message):
            try:
                data = json.loads(message)
                bids_raw = data.get("bids", [])
                asks_raw = data.get("asks", [])
                # Binance는 문자열로 오므로 float 변환
                bids = [(float(p), float(q), i + 1) for i, (p, q) in enumerate(bids_raw)]
                asks = [(float(p), float(q), i + 1) for i, (p, q) in enumerate(asks_raw)]
                if self._on_update:
                    self._on_update(bids, asks)
            except Exception:
                traceback.print_exc()

        def on_err(_ws, err):
            print("[BinanceGateway] error:", err)

        def on_close(_ws, *_):
            print("[BinanceGateway] closed")

        def run():
            self._ws = websocket.WebSocketApp(
                url,
                on_message=on_msg,
                on_error=on_err,
                on_close=on_close,
            )
            self._ws.run_forever()
            self._closed.set()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def close(self):
        try:
            if self._ws:
                self._ws.close()
            if self._thread and self._thread.is_alive():
                self._closed.wait(timeout=2.0)
        except Exception:
            pass
