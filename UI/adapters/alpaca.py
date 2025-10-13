# adapters/alpaca.py
# adapters/alpaca.py
import os
import datetime as dt
from dataclasses import dataclass
from typing import List, Tuple, Optional

import requests

ALPACA_DATA_BASE = "https://data.alpaca.markets/v2"   # Market Data v2
DEFAULT_FEED = os.getenv("ALPACA_FEED", "iex")        # 무료 플랜은 iex 권장


@dataclass
class Bar:
    ts: float   # epoch seconds (UTC)  ← app.py가 Candle(ts,...)로 쓰고 있으니 '초' 단위로 맞춥니다.
    o: float
    h: float
    l: float
    c: float
    v: int


def _iso_to_epoch_sec(s: str) -> float:
    # "2025-10-10T13:31:00Z" -> epoch seconds
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


class AlpacaSource:
    """app.py가 기대하는 인터페이스:
       - get_recent_bars(symbol, timeframe="1m", limit=300) -> List[Bar]
       - get_last_trade(symbol) -> Tuple[ts:int/float, price:float, size:int]
    """
    def __init__(self) -> None:
        key = (os.getenv("APCA-API-KEY-ID") or "").strip()
        sec = (os.getenv("APCA-API-SECRET-KEY") or "").strip()

        if not key or not sec:
            raise RuntimeError(
                "Alpaca API 키가 없습니다. 환경변수 APCA_API_KEY_ID / APCA_API_SECRET_KEY 를 설정하세요."
            )
        print(key)
        print(sec)
        print(DEFAULT_FEED)

        self.headers = {
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": sec
        }
        self.feed = DEFAULT_FEED

        # app.py는 "1m" 같은 약식을 넘깁니다 → Alpaca의 timeframe으로 매핑
        self._tf_map = {
            "1m": "1Min",
            "5m": "5Min",
            "15m": "15Min",
            "1h": "1Hour",
            "1d": "1Day",
            # 필요 시 추가
        }

    # ---------------------- public ----------------------
    def get_recent_bars(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 300,
        start: Optional[str] = None,  # "YYYY-MM-DDTHH:MM:SSZ" (UTC)
        end: Optional[str] = None,    # same format
    ) -> List[Bar]:
        tf = self._tf_map.get(timeframe.lower(), "1Min")
        # params = {
        #     "timeframe": tf,
        #     "start": "2025-10-10T00:00:00Z",
        #     "end": "2025-10-12T23:59:59Z",
        #     "limit": limit,
        #     "feed": self.feed,
        #     "adjustment": "raw",
        # }
        params = {
            "timeframe": "1Min",
            "start": "2025-10-08T00:00:00Z",
            "end": "2025-10-09T23:59:59Z",
            "limit": 300,
            "feed": "iex",
            "adjustment": "raw"
        }

        # if start:
        #     params["start"] = start
        # if end:
        #     params["end"] = end

        BASE = "https://data.alpaca.markets/v2"

        headers = {
            "APCA-API-KEY-ID": "PK7VDBLGNZWB6W351ME3",
            "APCA-API-SECRET-KEY": "CWIsbeLyjvQu3aFglp4YOO9iZjgjkmtNwCL1Svac"
        }
        params = {
            "timeframe": "1Min",
            "start": "2025-10-08T00:00:00Z",
            "end": "2025-10-09T23:59:59Z",
            "limit": 300,
            "feed": "iex",
            "adjustment": "raw"
        }

        url = f"{ALPACA_DATA_BASE}/stocks/{symbol}/bars"

        print(self.headers)

        r = requests.get(url, headers=self.headers, params=params, timeout=10)

        # r = requests.get(f"{BASE}/stocks/QQQ/bars", headers=headers, params=params)

        if r.status_code >= 400:
            raise RuntimeError(f"[Alpaca bars {symbol}] HTTP {r.status_code}: {r.text[:300]}")

        data = r.json() or {}
        bars = data.get("bars") or []
        out: List[Bar] = []
        for b in bars:
            try:
                ts = _iso_to_epoch_sec(b["t"])
                out.append(Bar(
                    ts=ts,
                    o=float(b["o"]),
                    h=float(b["h"]),
                    l=float(b["l"]),
                    c=float(b["c"]),
                    v=int(b.get("v", 0)),
                ))
            except Exception:
                # 잘못된 바는 스킵
                continue
        return out

    def get_last_trade(self, symbol: str) -> Tuple[float, float, int]:
        """마지막 체결 한 건. (ts, price, size) 반환. 없으면 예외."""
        url = f"{ALPACA_DATA_BASE}/stocks/trades/latest"
        params = {"symbol": symbol, "feed": self.feed}
        r = requests.get(url, headers=self.headers, params=params, timeout=10)

        if r.status_code >= 400:
            raise RuntimeError(f"[Alpaca latest trade {symbol}] HTTP {r.status_code}: {r.text[:300]}")

        data = r.json() or {}
        t = (data.get("trade") or {})
        if not t:
            raise RuntimeError(f"[Alpaca latest trade {symbol}] empty trade")

        ts = _iso_to_epoch_sec(t["t"])
        price = float(t["p"])
        size = int(t.get("s", 0))
        return ts, price, size


