# adapters/binance_oracle.py
import asyncio, json, threading, time, ssl
from typing import List, Tuple, Optional
import aiohttp

from models.depth import DepthSnapshot

class BinanceOracle:
    """
    Binance depth 오라클 유지 (심볼 예: 'SOLUSDT').
    - start(): 백그라운드에서 REST 스냅샷 + WS 업데이트
    - get_depth(levels): 최신 스냅샷을 DepthSnapshot으로 반환
    """
    def __init__(self, symbol: str = "SOLUSDT", levels: int = 10):
        self.symbol = symbol.upper()
        self.levels = int(levels)
        self._bids: List[Tuple[float, float]] = []
        self._asks: List[Tuple[float, float]] = []
        self._last_u: int = 0

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

        self._lock = threading.Lock()  # 스냅샷 보호

    # ---------- public ----------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run_loop, name="BinanceOracleLoop", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0):
        self._stop_evt.set()
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._shutdown_async(), self._loop)
        if self._thread:
            self._thread.join(timeout=timeout)

    def get_depth(self, levels: Optional[int] = None) -> Optional[DepthSnapshot]:
        """
        최신 호가를 DepthSnapshot으로 반환. (없으면 None)
        """
        lv = levels or self.levels
        with self._lock:
            if not self._bids and not self._asks:
                return None
            bids = [(p, int(s), 1) for (p, s) in self._bids[:lv]]
            asks = [(p, int(s), 1) for (p, s) in self._asks[:lv]]
        return DepthSnapshot(bids=bids, asks=asks, mid=DepthSnapshot.calc_mid(bids, asks))

    # ---------- internal ----------
    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())
        try:
            self._loop.close()
        except Exception:
            pass

    async def _shutdown_async(self):
        self._stop_evt.set()
        await asyncio.sleep(0.05)

    async def _main(self):
        ssl_ctx = ssl.create_default_context()
        async with aiohttp.ClientSession() as session:
            # 1) REST 스냅샷
            await self._rest_snapshot(session)
            # 2) WS 구독
            stream = f"{self.symbol.lower()}@depth@100ms"
            ws_url = f"wss://stream.binance.com:9443/ws/{stream}"
            while not self._stop_evt.is_set():
                try:
                    async with session.ws_connect(ws_url, ssl=ssl_ctx, heartbeat=20) as ws:
                        async for msg in ws:
                            if self._stop_evt.is_set():
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                j = json.loads(msg.data)
                                self._apply_update(j)
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                break
                except Exception:
                    # 잠시 쉬고 재접속
                    await asyncio.sleep(1.0)

    async def _rest_snapshot(self, session: aiohttp.ClientSession):
        url = f"https://api.binance.com/api/v3/depth?symbol={self.symbol}&limit=1000"
        async with session.get(url, timeout=10) as r:
            j = await r.json()
        bids = [(float(p), float(s)) for p, s in j["bids"]]
        asks = [(float(p), float(s)) for p, s in j["asks"]]
        with self._lock:
            self._bids = sorted(bids, key=lambda x: x[0], reverse=True)[:self.levels]
            self._asks = sorted(asks, key=lambda x: x[0])[:self.levels]
            self._last_u = int(j["lastUpdateId"])

    def _apply_update(self, data: dict):
        # data: contains U, u, b(업데이트 bids), a(업데이트 asks)
        if "U" not in data or "u" not in data:
            return
        U, u = int(data["U"]), int(data["u"])
        with self._lock:
            # 기본 필터: 예전 업데이트는 무시
            if u <= self._last_u:
                return
            self._last_u = u

            def apply(side_list, updates, reverse):
                d = {p: s for p, s in side_list}  # price->size
                for p, s in updates:
                    p = float(p); s = float(s)
                    if s == 0:
                        d.pop(p, None)
                    else:
                        d[p] = s
                new_list = sorted(d.items(), key=lambda x: x[0], reverse=reverse)[:self.levels]
                return new_list

            self._bids = apply(self._bids, data.get("b", []), True)
            self._asks = apply(self._asks, data.get("a", []), False)
