# services/marketdata_service.py
from __future__ import annotations
import requests
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional


# ---------------------------------------------
# DepthSnapshot 모델 (UI에서 그대로 사용)
# ---------------------------------------------
@dataclass
class DepthSnapshot:
    symbol: str
    bids: List[Tuple[float, float, int]]  # (price, qty, level)
    asks: List[Tuple[float, float, int]]
    mid: float


# ---------------------------------------------
# MarketDataService
# ---------------------------------------------
class MarketDataService:
    """
    BINANCE API 또는 LOCAL MATCHING ENGINE API에서 Depth를 불러와서
    UI가 사용하는 DepthSnapshot 형태로 반환하는 서비스.

    UI는 항상:
        md.fetch_depth() → DepthSnapshot

    형식에 의존하므로, 이 서비스만 교체하면 UI는 변경할 필요 없음.
    """

    def __init__(
        self,
        use_mock: bool = False,
        provider: str = "BINANCE",        # LOCAL or BINANCE
        symbol: str = "SOLUSDT",
        rows: int = 10,
        api_base: str = "http://127.0.0.1:9000"
    ):
        self.use_mock = use_mock
        self.provider = provider.upper()
        self._symbol = symbol.upper()
        self.rows = rows
        self.api_base = api_base     # LOCAL MATCHING ENGINE

    # -----------------------------------------
    # 심볼 제어
    # -----------------------------------------
    def current_symbol(self):
        return self._symbol

    def set_symbol(self, symbol: str):
        self._symbol = symbol.upper()

    # -----------------------------------------
    # 메인 엔트리
    # -----------------------------------------
    def fetch_depth(self) -> Optional[DepthSnapshot]:
        """
        provider에 따라 적절한 depth 소스를 호출한다.
        UI는 내부 구현과 상관없이 항상 DepthSnapshot만 받으면 된다.
        """
        if self.use_mock:
            return self._mock_depth()

        if self.provider == "LOCAL":
            return self._fetch_local_depth()

        elif self.provider == "BINANCE":
            return self._fetch_binance_depth()

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    # -----------------------------------------
    # 1) LOCAL MATCHING ENGINE DEPTH
    # -----------------------------------------
    def _fetch_local_depth(self) -> Optional[DepthSnapshot]:
        symbol = self._symbol

        try:
            url = f"{self.api_base}/orderbook"
            res = requests.get(url, params={"symbol": symbol}, timeout=0.5)

            if res.status_code != 200:
                print("[MarketDataService] local depth error", res.text)
                return None

            data = res.json()  # {bids:[...], asks:[...]}

            bids_raw = data.get("bids", [])
            asks_raw = data.get("asks", [])

            bids = [(float(x["price"]), float(x["qty"]), i) for i, x in enumerate(bids_raw)]
            asks = [(float(x["price"]), float(x["qty"]), i) for i, x in enumerate(asks_raw)]

            mid = self._calc_mid(bids, asks)

            return DepthSnapshot(symbol=symbol, bids=bids, asks=asks, mid=mid)

        except Exception as e:
            print("[MarketDataService] _fetch_local_depth error:", e)
            return None

    # -----------------------------------------
    # 2) BINANCE DEPTH
    # -----------------------------------------
    def _fetch_binance_depth(self) -> Optional[DepthSnapshot]:
        """
        https://api.binance.com/api/v3/depth?symbol=SOLUSDT&limit=20
        """
        try:
            url = f"https://api.binance.com/api/v3/depth?symbol={self._symbol}&limit={self.rows}"
            res = requests.get(url, timeout=3.0)
            if res.status_code != 200:
                print("[MarketDataService] binance error", res.text)
                return None

            data = res.json()
            bids_data = data.get("bids", [])
            asks_data = data.get("asks", [])

            bids = [(float(p), float(q), i) for i, (p, q) in enumerate(bids_data)]
            asks = [(float(p), float(q), i) for i, (p, q) in enumerate(asks_data)]

            mid = self._calc_mid(bids, asks)

            return DepthSnapshot(
                symbol=self._symbol,
                bids=bids,
                asks=asks,
                mid=mid
            )
        except Exception as e:
            print("[MarketDataService] BINANCE depth error:", e)
            return None

    # -----------------------------------------
    # MOCK DEPTH (테스트용)
    # -----------------------------------------
    def _mock_depth(self) -> DepthSnapshot:
        import random
        base = 20000 + random.uniform(-50, 50)
        bids = []
        asks = []

        for i in range(self.rows):
            bids.append((base - i * 5, random.randint(1, 10), i))
            asks.append((base + i * 5, random.randint(1, 10), i))

        mid = (bids[0][0] + asks[0][0]) / 2
        return DepthSnapshot(self._symbol, bids, asks, mid)

    # -----------------------------------------
    # mid 계산
    # -----------------------------------------
    def _calc_mid(self, bids, asks):
        if bids and asks:
            return (bids[0][0] + asks[0][0]) / 2
        return 0.0

    # -----------------------------------------
    # UI BalanceTable에서 사용
    # -----------------------------------------
    def get_last_price(self, symbol: Optional[str] = None):
        """
        특정 심볼의 mid price만 간단히 가져오기 (잔고 평가용)
        """
        symbol = (symbol or self._symbol).upper()
        depth = self._fetch_local_depth() if self.provider == "LOCAL" else self.fetch_depth()

        if not depth:
            return None
        return depth.mid

    def get_latest_prices_dict(self):
        """BalanceTable.render_positions()에서 사용하기 좋은 형태"""
        depth = self.fetch_depth()
        if not depth:
            return {}
        return {self._symbol: depth.mid}

    def get_mid_price(self):
        depth = self.fetch_depth()

        if not depth or not depth.bids or not depth.asks:
            return None

        best_bid = depth.bids[0][0]  # (price, qty, level)
        best_ask = depth.asks[0][0]

        return (best_bid + best_ask) / 2

