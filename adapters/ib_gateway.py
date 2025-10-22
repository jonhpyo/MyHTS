from typing import Optional
from ib_insync import IB, Future

class IBGateway:
    def __init__(self, host='127.0.0.1', port=7497, client_id=100):
        self.ib = IB()
        self.host, self.port, self.client_id = host, port, client_id
        self.ticker = None

    def connect(self):
        self.ib.connect(self.host, self.port, clientId=self.client_id)
        self.ib.reqMarketDataType(1)

    def subscribe_depth(self, symbol='NQ', expiry='202512', exchange='CME', rows=10):
        contract = Future(symbol, expiry, exchange)
        self.ib.qualifyContracts(contract)
        self.ticker = self.ib.reqMktDepth(contract, numRows=rows)
        return self.ticker

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
                self.ib.cancelMktDepth(self.ticker.contract)
            if self.ib.isConnected():
                self.ib.disconnect()
        except Exception:
            pass
