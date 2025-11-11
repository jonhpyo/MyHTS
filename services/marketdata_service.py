import os
import time
import random
from typing import Optional

from adapters.binance_gateway import BinanceGateway
from adapters.binance_oracle import BinanceOracle
from adapters.ib_gateway import IBGateway
from models.depth import DepthSnapshot


class MarketDataService:
    """
    실제 피드(IB / BINANCE / ORACLE) 또는 Mock 으로 Depth 스냅샷을 제공.

    - use_mock=True  : 매 호출마다 랜덤으로 생성
    - use_mock=False : provider 에 따라
        * IB       -> IBGateway.subscribe_depth 콜백 캐시 사용
        * BINANCE  -> BinanceGateway.depth 스트림 콜백 캐시 사용
        * ORACLE   -> BinanceOracle.get_depth() 폴링
    """

    def __init__(
        self,
        use_mock: bool,
        base_price: float = 20000.0,
        provider: str = None,
        symbol: str = None,
        expiry: str = None,
        exchange: str = None,
        rows: int = 10,
        fallback_after_sec: float = 3.0,
    ):
        self.use_mock = use_mock
        self.base_price = base_price
        self.provider = (provider or os.getenv("MD_PROVIDER", "IB")).upper()
        self.symbol = (symbol or os.getenv("SYMBOL", "btcusdt")).lower()
        self.expiry = expiry or os.getenv("IB_EXPIRY", "202512")
        self.exchange = exchange or os.getenv("IB_EXCHANGE", "CME")
        self.rows = rows
        self.fallback_after_sec = fallback_after_sec

        self.ib: Optional[IBGateway] = None
        self._oracle: Optional[BinanceOracle] = None
        self.binance: Optional[BinanceGateway] = None
        self._last_snapshot: Optional[DepthSnapshot] = None
        self._started_at: Optional[float] = None
        self._fallback_armed = not self.use_mock  # 나중에 타임아웃 폴백 구현 예정

    # ---------- 심볼 관련 ----------
    def set_symbol(self, sym: str):
        """심볼 전환 시 스트림 재시작 및 내부 상태 초기화"""
        new_sym = sym.lower() if self.provider == "BINANCE" else sym.upper()
        if new_sym == self.symbol:
            return

        self.symbol = new_sym
        print("[MarketDataService] set_symbol ->", self.symbol)

        # # 🔹 이전 오라클 정리
        # if self._oracle:
        #     try:
        #         self._oracle.stop()
        #     except Exception as e:
        #         print("[MarketDataService] oracle.stop error:", e)
        #     self._oracle = None

        # 기존 스트림/구독 정리
        try:
            self.close()
        except Exception:
            pass

        # 프로바이더에 맞게 다시 시작
        if not self.use_mock:
            if self.provider == "BINANCE":
                self.start_binance()
            elif self.provider == "IB":
                self.start_ib()
            else:  # ORACLE 기타
                self.start_oracle()

        # 내부 캐시/버퍼 초기화
        self._clear_buffers()

    def current_symbol(self) -> str:
        return self.symbol.upper()

    def _clear_buffers(self):
        """심볼 전환 시 내부 캐시/버퍼 초기화"""
        self._last_snapshot = None
        self._started_at = None

    # ---------- IB ----------
    def start_ib(self):
        if self.use_mock or self.provider != "IB":
            return

        self.ib = IBGateway(
            host=os.getenv("IB_HOST", "127.0.0.1"),
            port=int(os.getenv("IB_PORT", "7497")),
            client_id=int(os.getenv("IB_CLIENT_ID", "100")),
        )
        print("start ib")
        self.ib.connect()
        self._started_at = time.time()

        def on_update(bids, asks):
            print("IB on_update", bids, asks)
            mid = DepthSnapshot.calc_mid(bids, asks)
            self._last_snapshot = DepthSnapshot(bids=list(bids), asks=list(asks), mid=mid)
            self._last_snapshot.symbol = self.current_symbol()

        self.ib.subscribe_depth(
            symbol=self.current_symbol(),
            expiry=self.expiry,
            exchange=self.exchange,
            rows=self.rows,
            on_update=on_update,
            smart_depth=False,
        )

    # ---------- ORACLE (BinanceOracle 폴링용) ----------
    def start_oracle(self):
        if self.use_mock:
            return
        if self._oracle:
            return

        self._oracle = BinanceOracle(symbol=self.symbol, levels=self.rows)
        self._oracle.start()
        self._started_at = time.time()

    # ---------- BINANCE ----------
    def start_binance(self):
        if self.use_mock or self.provider != "BINANCE":
            return

        self.binance = BinanceGateway(symbol=self.symbol, rows=self.rows, interval_ms=100)
        self._started_at = time.time()

        def on_update(bids, asks):
            mid = DepthSnapshot.calc_mid(bids, asks)
            self._last_snapshot = DepthSnapshot(bids=bids, asks=asks, mid=mid)
            self._last_snapshot.symbol = self.current_symbol()

        self.binance.connect(on_update=on_update)

    # ---------- 스냅샷 제공 ----------
    def fetch_depth(self) -> Optional[DepthSnapshot]:
        # MOCK 모드
        if self.use_mock:
            snap = self._gen_mock_depth()
            if snap and getattr(snap, "symbol", None) is None:
                snap.symbol = self.current_symbol()
            return snap

        # 콜백 기반 피드(IB / BINANCE): 마지막 캐시 우선 사용
        if self._last_snapshot:
            cur = self.current_symbol()
            last_sym = getattr(self._last_snapshot, "symbol", cur)
            if last_sym == cur:
                return self._last_snapshot
            else:
                # 심볼 달라졌으면 폐기
                self._last_snapshot = None

        # ORACLE 방식일 때만 직접 폴링
        if self.provider == "ORACLE":
            if not self._oracle:
                return None
            snap = self._oracle.get_depth(levels=self.rows)
            if snap and getattr(snap, "symbol", None) is None:
                snap.symbol = self.current_symbol()
            return snap

        # 아직 데이터가 안 들어왔으면 fallback
        if (
            self._fallback_armed
            and self._started_at
            and (time.time() - self._started_at) > self.fallback_after_sec
        ):
            # print("⚠️ No depth update yet, switching to mock for safety.")
            return self._gen_mock_depth()

        return None

    # ---------- 종료 ----------
    def close(self):
        if self.ib:
            self.ib.close()
            self.ib = None
        if self.binance:
            self.binance.close()
            self.binance = None
        if self._oracle:
            self._oracle.stop()
            self._oracle = None

        self._clear_buffers()

    # ---------- 목데이터 ----------
    def _gen_mock_depth(self) -> DepthSnapshot:
        bids = [
            (self.base_price - i * 2 - random.random(), random.randint(1, 5), 1)
            for i in range(self.rows)
        ]
        asks = [
            (self.base_price + i * 2 + random.random(), random.randint(1, 5), 1)
            for i in range(self.rows)
        ]
        mid = (bids[0][0] + asks[0][0]) / 2.0
        snap = DepthSnapshot(bids, asks, mid)
        snap.symbol = self.current_symbol()
        return snap
