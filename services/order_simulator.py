from typing import List, Tuple
from models.depth import DepthSnapshot
from models.order import Side, Fill
from models.working_order import WorkingOrder

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
    def sell_limit_now_or_queue(self, price: float, qty: int, depth) -> tuple[list[Fill], object, int]:
        """
        지정가 매도:
        - 호가창(depth)에서 매수호가와 맞춰 즉시 체결할 수 있는 만큼 체결
        - 남는 잔량이 있으면 WorkingOrder 로 self.working 에 등록
        반환: (fills, new_depth, remain)
        """
        fills: list[Fill] = []
        remain = qty

        # 1) depth 에서 즉시 체결 가능한 부분 매칭 (예: 최우선 bid부터 탐색)
        bids = list(depth.bids)  # [(price, qty, level), ...] 가정
        new_bids = []
        for bp, bqty, level in bids:
            if remain <= 0:
                new_bids.append((bp, bqty, level))
                continue

            if bp >= price:
                # 이 가격 이상이면 체결
                trade_qty = min(remain, bqty)
                fills.append(
                    Fill(
                        side=Side.SELL,
                        price=bp,
                        qty=trade_qty,
                        symbol=getattr(depth, "symbol", None),
                    )
                )
                remain -= trade_qty
                rest = bqty - trade_qty
                if rest > 0:
                    new_bids.append((bp, rest, level))
            else:
                new_bids.append((bp, bqty, level))

        # asks 는 그대로 사용 (매도니까 매수호가만 소진)
        new_asks = list(depth.asks)

        # 2) 남은 잔량을 WorkingOrder 로 미체결 등록
        if remain > 0:
            order_id = len(self.working) + 1  # 간단한 내부 ID
            wo = WorkingOrder(
                id=order_id,
                side=Side.SELL,
                price=price,
                qty=qty,
                remaining=remain,
            )
            self.working.append(wo)

        # 3) new_depth 구성 (DepthSnapshot 을 다시 만들어 돌려줌)
        new_mid = depth.mid  # 필요하면 재계산
        new_depth = type(depth)(bids=new_bids, asks=new_asks, mid=new_mid)
        setattr(new_depth, "symbol", getattr(depth, "symbol", None))

        return fills, new_depth, remain

    # --- 지정가(BUY) ---
    def buy_limit_now_or_queue(self, price: float, qty: int, depth) -> tuple[list[Fill], object, int]:
        """
        지정가 매도:
        - 호가창(depth)에서 매수호가와 맞춰 즉시 체결할 수 있는 만큼 체결
        - 남는 잔량이 있으면 WorkingOrder 로 self.working 에 등록
        반환: (fills, new_depth, remain)
        """
        fills: list[Fill] = []
        remain = qty

        # 1) depth 에서 즉시 체결 가능한 부분 매칭 (예: 최우선 bid부터 탐색)
        bids = list(depth.bids)  # [(price, qty, level), ...] 가정
        new_bids = []
        for bp, bqty, level in bids:
            if remain <= 0:
                new_bids.append((bp, bqty, level))
                continue

            if bp >= price:
                # 이 가격 이상이면 체결
                trade_qty = min(remain, bqty)
                fills.append(
                    Fill(
                        side=Side.SELL,
                        price=bp,
                        qty=trade_qty,
                        symbol=getattr(depth, "symbol", None),
                    )
                )
                remain -= trade_qty
                rest = bqty - trade_qty
                if rest > 0:
                    new_bids.append((bp, rest, level))
            else:
                new_bids.append((bp, bqty, level))

        # asks 는 그대로 사용 (매도니까 매수호가만 소진)
        new_asks = list(depth.asks)

        # 2) 남은 잔량을 WorkingOrder 로 미체결 등록
        if remain > 0:
            order_id = len(self.working) + 1  # 간단한 내부 ID
            wo = WorkingOrder(
                id=order_id,
                side=Side.SELL,
                price=price,
                qty=qty,
                remaining=remain,
            )
            self.working.append(wo)

        # 3) new_depth 구성 (DepthSnapshot 을 다시 만들어 돌려줌)
        new_mid = depth.mid  # 필요하면 재계산
        new_depth = type(depth)(bids=new_bids, asks=new_asks, mid=new_mid)
        setattr(new_depth, "symbol", getattr(depth, "symbol", None))

        return fills, new_depth, remain

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
