# ib_depth_bridge.py
from __future__ import annotations
from typing import Callable, List, Tuple, Optional
from ib_insync import *
import threading
import time
from ib_insync import util
util.useQt()   # PyQt5/6 자동 연동

Depth = Tuple[float, int, int]  # (price, size, count)

class IBDepthBridge:
    def __init__(
        self,
        on_depth: Callable[[List[Depth], List[Depth], Optional[float]], None],
        symbol: str = "NQ",
        yyyymm: str = "202512",
        exchange: str = "CME",
        host: str = "127.0.0.1",
        port: int = 7497,        # TWS Paper=7497, Gateway Paper=4002
        client_id: int = 100,
        depth_rows: int = 10,
        reconnect_sec: int = 5,
    ):
        self.on_depth = on_depth
        self.symbol = symbol
        self.yyyymm = yyyymm
        self.exchange = exchange
        self.host = host
        self.port = port
        self.client_id = client_id
        self.depth_rows = depth_rows
        self.reconnect_sec = reconnect_sec

        self.ib = IB()
        self._ticker: Optional[Ticker] = None
        self._stop = False
        self._th: Optional[threading.Thread] = None

    def start(self):
        if self._th and self._th.is_alive():
            return
        self._stop = False
        self._th = threading.Thread(target=self._run, daemon=True)
        self._th.start()

    def stop(self):
        self._stop = True
        try:
            if self._ticker:
                self.ib.cancelMktDepth(self._ticker.contract)
        except Exception:
            pass
        try:
            if self.ib.isConnected():
                self.ib.disconnect()
        except Exception:
            pass

    def change_contract(self, symbol: str, yyyymm: str, exchange: str = "CME"):
        """실행 중 심볼/월물 교체."""
        self.symbol = symbol
        self.yyyymm = yyyymm
        self.exchange = exchange
        # 재구독
        try:
            if self._ticker:
                self.ib.cancelMktDepth(self._ticker.contract)
        except Exception:
            pass
        self._ticker = None

    def _connect(self) -> bool:
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=5)
            print(f"[IB] Connected: {self.ib.isConnected()} host={self.host} port={self.port}")
            return self.ib.isConnected()
        except Exception as e:
            print("[IB] Connect failed:", e)
            return False

    def _subscribe_depth(self) -> bool:
        try:
            contract = Future(self.symbol, self.yyyymm, self.exchange, currency="USD")
            self.ib.qualifyContracts(contract)
            # 심볼/월물 확인 로그
            details = self.ib.reqContractDetails(contract) or []
            if details:
                cd = details[0]
                print(f"[IB] Contract qualified: {cd.contract.symbol} {cd.contract.lastTradeDateOrContractMonth} {cd.contract.exchange}")
            else:
                print("[IB] Warning: No contract details found")

            self._ticker = self.ib.reqMktDepth(contract, numRows=self.depth_rows)
            print(f"[IB] Subscribed market depth: {self.symbol} {self.yyyymm} rows={self.depth_rows}")
            return True
        except Exception as e:
            print("[IB] reqMktDepth failed:", e)
            # 흔한 원인: 354 (market data subscription 없음), 10167(not authorized)
            return False

    def _emit_depth(self):
        if not self._ticker:
            return
        bids: List[Depth] = []
        asks: List[Depth] = []
        try:
            for row in self._ticker.domBids:
                if row.price is None:
                    continue
                bids.append((float(row.price), int(row.size or 0), 1))
            for row in self._ticker.domAsks:
                if row.price is None:
                    continue
                asks.append((float(row.price), int(row.size or 0), 1))
        except Exception:
            return
        if not bids and not asks:
            return
        mid = None
        if bids and asks:
            mid = (bids[0][0] + asks[0][0]) / 2.0
        self.on_depth(bids, asks, mid)

    def _run(self):
        while not self._stop:
            if not self.ib.isConnected():
                if not self._connect():
                    time.sleep(self.reconnect_sec)
                    continue

            # (재)구독
            if not self._ticker:
                if not self._subscribe_depth():
                    # 권한 미보유/미구독 시 여기서 루프 휴식
                    print("[IB] Depth subscribe failed. Check market data subscriptions (CME L1/L2). Retrying...")
                    time.sleep(self.reconnect_sec)
                    continue

            try:
                # 업데이트 대기 + 반영
                self.ib.waitOnUpdate(timeout=1.0)
                self._emit_depth()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print("[IB] loop error:", e)
                time.sleep(1)

        # clean up
        self.stop()
