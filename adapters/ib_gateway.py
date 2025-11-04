# ib_gateway.py
from typing import Optional, Callable, List, Tuple
from ib_insync import IB, Future, Ticker
from ib_insync.contract import ContractDetails

class IBGateway:
    def __init__(self, host='127.0.0.1', port=7497, client_id=100):
        self.ib = IB()
        self.host, self.port, self.client_id = host, port, client_id
        self.ticker: Optional[Ticker] = None

    def connect(self):
        self.ib.connect(self.host, self.port, clientId=self.client_id)
        # 1=LIVE, 3=DELAYED — Depth는 지연 제공 거의 없음
        self.ib.reqMarketDataType(1)

        # 에러 로깅 도움
        self.ib.errorEvent += lambda reqId, code, msg, *_: print(f"[IB] err {code}: {msg}")

    def resolve_contract(self, symbol='NQ', expiry='202512', exchange='CME'):
        """
        컨트랙트 디테일로 conId를 확정해 안정적으로 Depth 구독.
        """
        c = Future(symbol=symbol, lastTradeDateOrContractMonth=expiry, exchange=exchange, currency='USD')
        details: List[ContractDetails] = self.ib.reqContractDetails(c)
        if not details:
            # GLOBEX로 재시도
            c2 = Future(symbol=symbol, lastTradeDateOrContractMonth=expiry, exchange='GLOBEX', currency='USD')
            details = self.ib.reqContractDetails(c2)
            if not details:
                raise RuntimeError(f"Contract not found: {symbol} {expiry} {exchange}")
            c = details[0].contract
        else:
            c = details[0].contract
        return c

    def subscribe_depth(self, symbol='NQ', expiry='202512', exchange='CME', rows=10,
                        on_update: Optional[Callable[[list, list], None]] = None,
                        smart_depth: bool = False):
        """
        Depth 구독 + 콜백 등록. on_update(bids, asks)
        """
        print('subscribe_depth')
        contract = self.resolve_contract(symbol, expiry, exchange)
        self.ticker = self.ib.reqMktDepth(contract, numRows=rows, isSmartDepth=smart_depth)

        if on_update:
            def _on_tick(_tk: Ticker):
                bids = [(float(r.price), int(r.size or 0), 1) for r in _tk.domBids if r.price is not None]
                asks = [(float(r.price), int(r.size or 0), 1) for r in _tk.domAsks if r.price is not None]
                on_update(bids, asks)
            self.ticker.updateEvent += _on_tick

        print(self.ticker)
        return self.ticker

    def wait_first_update(self, timeout=3.0) -> Tuple[list, list]:
        """
        첫 DOM 업데이트가 들어올 때까지 잠깐 대기 (Qt / asyncio 루프가 돌아야 함).
        """
        self.ib.waitOnUpdate(timeout)
        return self.dom_bids(), self.dom_asks()

    def dom_bids(self):
        if not self.ticker:
            return []
        return [(float(r.price), int(r.size or 0), 1) for r in self.ticker.domBids if r.price is not None]

    def dom_asks(self):
        if not self.ticker:
            return []
        return [(float(r.price), int(r.size or 0), 1) for r in self.ticker.domAsks if r.price is not None]

    def close(self):
        try:
            if self.ticker:
                # cancelMktDepth는 Ticker가 아니라 Contract/reqId 기준이라 다음처럼 안전하게:
                self.ib.cancelMktDepth(self.ticker.contract)
            if self.ib.isConnected():
                self.ib.disconnect()
        except Exception as e:
            print("IB close error:", e)
