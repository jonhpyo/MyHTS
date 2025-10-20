# databento_bridge.py
from __future__ import annotations
import os, threading, time
from typing import Callable, List, Optional, Tuple
from dotenv import load_dotenv

Depth = Tuple[float, int, int]  # (price, qty, cnt)

class DatabentoBridge:
    """
    Databento Live API → on_depth(bids, asks, mid) 콜백 전달
    - dataset: GLBX.MDP3 (CME Globex)
    - schema : bbo (또는 tbbo)
    - symbols: NQ.FUT (부모 심볼; ES는 ES.FUT, MNQ는 MNQ.FUT)
    """
    def __init__(
        self,
        on_depth: Callable[[List[Depth], List[Depth], Optional[float]], None],
        dataset: str = "GLBX.MDP3",
        schema: str = "bbo",
        symbols: str = "NQ.FUT",
        stype_in: str = "parent",
    ):
        load_dotenv()
        self.api_key = os.getenv("DATABENTO_API_KEY")
        if not self.api_key:
            raise RuntimeError("DATABENTO_API_KEY가 .env에 없습니다.")
        self.on_depth = on_depth
        self.dataset = dataset
        self.schema = schema
        self.symbols = symbols
        self.stype_in = stype_in

        self._stop = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True

    def _run(self):
        import databento as db
        print(f"[DB] connecting live: dataset={self.dataset} schema={self.schema} symbols={self.symbols}")
        live = db.Live(key=self.api_key)

        # 콜백 방식: 레코드 하나 들어올 때마다 on_record 호출
        def on_record(rec):
            if self._stop:
                return
            # bbo/tbbo 공통: bid_px, bid_sz, ask_px, ask_sz
            bid_px = getattr(rec, "bid_px", None)
            bid_sz = getattr(rec, "bid_sz", None)
            ask_px = getattr(rec, "ask_px", None)
            ask_sz = getattr(rec, "ask_sz", None)
            if bid_px is None and ask_px is None:
                return

            bids: List[Depth] = []
            asks: List[Depth] = []
            try:
                if bid_px is not None and (bid_sz or 0) > 0:
                    bids.append((float(bid_px), int(bid_sz), 1))
                if ask_px is not None and (ask_sz or 0) > 0:
                    asks.append((float(ask_px), int(ask_sz), 1))
            except Exception:
                return

            if not bids and not asks:
                return
            mid = None
            if bids and asks:
                mid = (bids[0][0] + asks[0][0]) / 2.0
            self.on_depth(bids, asks, mid)

        live.add_callback(on_record)

        # 구독 시작
        try:
            live.subscribe(
                dataset=self.dataset,
                schema=self.schema,          # "bbo" 또는 "tbbo"
                symbols=self.symbols,        # "NQ.FUT", "ES.FUT", "MNQ.FUT" 등
                stype_in=self.stype_in,      # "parent"
            )
            # 블로킹 실행 (스레드 내에서 유지)
            live.start()
        except Exception as e:
            print("[DB ERROR]", e)

        # 종료 루프(옵션)
        while not self._stop:
            time.sleep(0.5)
        try:
            live.stop()
        except Exception:
            pass
        print("[DB] stopped")
