# services/marketdata_service.py
import os
import time
import random
from typing import Optional, Tuple, Callable

from adapters.binance_gateway import BinanceGateway
from adapters.binance_oracle import BinanceOracle
from models.depth import DepthSnapshot
from adapters.ib_gateway import IBGateway
from adapters.binance_gateway import BinanceGateway

class MarketDataService:
    """
    실제 IB 또는 Mock 로 Depth 스냅샷을 제공.
    - IB: subscribe_depth 콜백으로 최신 스냅샷을 캐싱하고, fetch_depth()는 그 캐시를 반환
    - MOCK: 매 호출마다 랜덤으로 생성
    - 시작 후 일정 시간(예: 3초) 내 업데이트가 없으면 MOCK으로 폴백 옵션
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
        fallback_after_sec: float = 3.0
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
        self._fallback_armed = not self.use_mock  # IB 모드일 때만 폴백 감시

    def set_symbol(self, sym: str):
        # 프로바이더 규칙에 따라 정규화
        new_sym = sym.lower() if self.provider == "BINANCE" else sym.upper()
        if new_sym == self._symbol:
            return  # 변화 없으면 그대로

        self._symbol = new_sym

        # 스트림/구독 재설정
        try:
            self.close()  # 이전 구독 정리 (이미 있다면)
        except Exception:
            pass

        if not self.use_mock:
            # 사용 중인 피드 재시작 (프로젝트에 맞춰 사용)
            if hasattr(self, "start_oracle"):
                self.start_oracle()
            elif hasattr(self, "start_binance"):
                self.start_binance()
            elif hasattr(self, "start_ib"):
                self.start_ib()
        # 내부 캐시/버퍼 비우기 (심볼별 상태가 섞이지 않게)
        if hasattr(self, "_clear_buffers"):
            self._clear_buffers

    def current_symbol(self) -> str:
        return self.symbol.upper()


    # ---- IB 시작 ----
    def start_ib(self):
        if self.use_mock:
            return
        self.ib = IBGateway(
            host=os.getenv("IB_HOST", "127.0.0.1"),
            port=int(os.getenv("IB_PORT", "7497")),
            client_id=int(os.getenv("IB_CLIENT_ID", "100")),
        )
        print('start ib')
        self.ib.connect()
        self._started_at = time.time()

        def on_update(bids, asks):
            print('on_update' + bids, asks)
            mid = DepthSnapshot.calc_mid(bids, asks)
            # 캐시
            self._last_snapshot = DepthSnapshot(bids=list(bids), asks=list(asks), mid=mid)

        # 심볼/월물/거래소 파라미터 반영해서 구독
        self.ib.subscribe_depth(
            symbol=os.getenv("SYMBOL", self.symbol.upper()),
            expiry=self.expiry,
            exchange=self.exchange,
            rows=self.rows,
            on_update=on_update,
            smart_depth=False,  # 필요 시 True로 변경
        )

    def start_oracle(self):
        if self.use_mock:
            return
        if self._oracle:
            return
        self._oracle = BinanceOracle(symbol=self.symbol, levels=self.rows)
        self._oracle.start()

    def start_binance(self):
        if self.use_mock or self.provider != "BINANCE":
            return
        self.binance = BinanceGateway(symbol=self.symbol, rows=self.rows, interval_ms=100)
        self._started_at = time.time()

        def on_update(bids, asks):
            mid = DepthSnapshot.calc_mid(bids, asks)
            self._last_snapshot = DepthSnapshot(bids=bids, asks=asks, mid=mid)

        self.binance.connect(on_update=on_update)

    # ---- 스냅샷 제공 ----
    def fetch_depth(self) -> Optional[DepthSnapshot]:
        # MOCK
        if self.use_mock:
            snap = self._gen_mock_depth()
            if snap and getattr(snap, "symbol", None) is None:
                snap.symbol = self.current_symbol()
            return snap

        # IB/Push: 마지막 스냅샷이 있더라도 "심볼이 현재와 같은지" 확인
        if self._last_snapshot:
            cur = self.current_symbol()
            last_sym = getattr(self._last_snapshot, "symbol", cur)
            if last_sym == cur:
                return self._last_snapshot
            else:
                # 다른 심볼이면 폐기
                self._last_snapshot = None

        if not self._oracle:
            return None

        snap = self._oracle.get_depth(levels=self.rows)  # 오라클이 현재 심볼 기준으로 동작해야 함
        # 스냅샷에 심볼 태그 보강
        if snap and getattr(snap, "symbol", None) is None:
            snap.symbol = self.current_symbol()
        return snap

    # ---- 종료 ----
    def close(self):
        if self.ib: self.ib.close()
        if self.binance: self.binance.close()
        if self._oracle:
            self._oracle.stop()
            self._oracle = None

    # ---- 유틸: 목데이터 생성 ----
    def _gen_mock_depth(self) -> DepthSnapshot:
        bids = [(self.base_price - i * 2 - random.random(), random.randint(1, 5), 1) for i in range(self.rows)]
        asks = [(self.base_price + i * 2 + random.random(), random.randint(1, 5), 1) for i in range(self.rows)]
        mid = (bids[0][0] + asks[0][0]) / 2.0
        return DepthSnapshot(bids, asks, mid)
