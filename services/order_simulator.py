from typing import List, Tuple
from models.depth import DepthSnapshot
from models.order import WorkingOrder, Fill

class OrderSimulator:
    """시장가/지정가 체결 로직 + 미체결(대기) 관리."""
    def __init__(self):
        self.working: List[WorkingOrder] = []

    # --- 시장가 ---
    def sell_market(self, qty: int, depth: DepthSnapshot) -> Tuple[List[Fill], DepthSnapshot]:
        bids = list(depth.bids)
        asks = list(depth.asks)
        remaining = qty
        fills: List[Fill] = []
        new_bids = []
        for px, sz, lv in bids:
            if remaining <= 0:
                new_bids.append((px, sz, lv)); continue
            take = min(sz, remaining)
            if take > 0:
                fills.append(Fill("SELL", px, take))
            remaining -= take
            new_bids.append((px, sz - take, lv))
        new_mid = DepthSnapshot.calc_mid(new_bids, asks) or depth.mid
        return (fills, DepthSnapshot(new_bids, asks, new_mid))

    def buy_market(self, qty: int, depth: DepthSnapshot) -> Tuple[List[Fill], DepthSnapshot]:
        bids = list(depth.bids)
        asks = list(depth.asks)
        remaining = qty
        fills: List[Fill] = []
        new_asks = []
        for px, sz, lv in asks:
            if remaining <= 0:
                new_asks.append((px, sz, lv)); continue
            take = min(sz, remaining)
            if take > 0:
                fills.append(Fill("BUY", px, take))
            remaining -= take
            new_asks.append((px, sz - take, lv))
        new_mid = DepthSnapshot.calc_mid(bids, new_asks) or depth.mid
        return (fills, DepthSnapshot(bids, new_asks, new_mid))

    # --- 지정가(SELL) ---
    def sell_limit_now_or_queue(self, price: float, qty: int, depth: DepthSnapshot) -> Tuple[List[Fill], DepthSnapshot, int]:
        bids = list(depth.bids)
        asks = list(depth.asks)
        remain = qty
        fills: List[Fill] = []

        for i, (bp, bs, lv) in enumerate(bids):
            if remain <= 0:
                break
            if bp < price:
                break
            take = min(bs, remain)
            if take > 0:
                fills.append(Fill("SELL", bp, take))
                remain -= take
                bids[i] = (bp, bs - take, lv)

        new_mid = DepthSnapshot.calc_mid(bids, asks) or depth.mid
        new_depth = DepthSnapshot(bids, asks, new_mid)

        if remain > 0:
            self.working.append(WorkingOrder("SELL", price, remain, "LMT"))
        return (fills, new_depth, remain)

    # --- 미체결 자동 매칭 (현재 SELL만) ---
    def match_working_on_depth(self, depth: DepthSnapshot) -> Tuple[List[Fill], DepthSnapshot]:
        if not self.working:
            return ([], depth)

        bids = list(depth.bids)
        asks = list(depth.asks)
        fills: List[Fill] = []
        remains: List[WorkingOrder] = []

        for od in self.working:
            if od.side == "SELL":
                need = od.qty
                for i, (bp, bs, lv) in enumerate(bids):
                    if need <= 0: break
                    if bp < od.price: break
                    take = min(bs, need)
                    if take > 0:
                        fills.append(Fill("SELL", bp, take))
                        need -= take
                        bids[i] = (bp, bs - take, lv)
                if need > 0:
                    od.qty = need
                    remains.append(od)
            else:
                remains.append(od)  # BUY 지정가 대칭 로직 필요시 추가

        self.working = remains
        new_mid = DepthSnapshot.calc_mid(bids, asks) or depth.mid
        return (fills, DepthSnapshot(bids, asks, new_mid))
