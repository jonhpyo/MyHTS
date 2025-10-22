import random
from typing import Optional
from models.depth import DepthSnapshot
from adapters.ib_gateway import IBGateway

class MarketDataService:
    """실제 IB 또는 Mock 로 Depth 스냅샷을 제공."""
    def __init__(self, use_mock: bool, base_price: float = 20000.0):
        self.use_mock = use_mock
        self.base_price = base_price
        self.ib: Optional[IBGateway] = None

    def start_ib(self):
        self.ib = IBGateway()
        self.ib.connect()
        self.ib.subscribe_depth()

    def fetch_depth(self) -> Optional[DepthSnapshot]:
        if self.use_mock:
            bids = [(self.base_price - i * 2 - random.random(), random.randint(1, 5), 1) for i in range(10)]
            asks = [(self.base_price + i * 2 + random.random(), random.randint(1, 5), 1) for i in range(10)]
            mid = (bids[0][0] + asks[0][0]) / 2
            return DepthSnapshot(bids, asks, mid)

        if not self.ib:
            return None
        bids = self.ib.dom_bids()
        asks = self.ib.dom_asks()
        if not bids and not asks:
            return None
        return DepthSnapshot(bids, asks, DepthSnapshot.calc_mid(bids, asks))

    def close(self):
        if self.ib:
            self.ib.close()
