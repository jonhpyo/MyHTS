# datasource_yf.py
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Tuple
import yfinance as yf

@dataclass
class Row:
    name: str
    code: str
    price: float | None
    change_pct: float | None

class YFSource:
    """
    야후 파이낸스 기반 단순 시세 소스.
    - 지수/FX/선물 혼합 지원
    - 전일 종가 대비 등락률 계산
    """
    # 사용자가 원한 종목들(가용 심볼로 매핑)
    # * 코스피 선물의 무료 심볼을 구하기 어려워 코스피 지수(^KS11)로 대체
    # * 미니항셍은 공개 심볼 제공이 불안정 -> 항셍지수(^HSI)로 대체
    UNIVERSE: List[Tuple[str, str]] = [
        ("코스피 (지수 대체)", "^KS11"),
        ("S&P 500", "^GSPC"),
        ("미니항셍 (항셍 지수 대체)", "^HSI"),
        ("항셍지수", "^HSI"),
        ("유로화 (EUR/USD)", "EURUSD=X"),
        ("은 선물", "SI=F"),
        ("나스닥100", "^NDX"),
        ("마이크로 금 선물", "MGC=F"),
        ("영국 파운드 (GBP/USD)", "GBPUSD=X"),
        ("호주달러 (AUD/USD)", "AUDUSD=X"),
        ("금 선물", "GC=F"),
        ("크루드 오일 (WTI) 선물", "CL=F"),
    ]

    def fetch(self) -> List[Row]:
        tickers = [code for _, code in self.UNIVERSE]
        # 5영업일 일봉 받아서 '마지막 종가'와 '직전 종가'로 등락률 계산
        # (지수/FX/선물 혼합이므로 일봉이 가장 안전)
        df = yf.download(
            tickers=" ".join(tickers),
            period="10d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False,
        )

        rows: List[Row] = []
        for name, code in self.UNIVERSE:
            try:
                # 단일 심볼일 때와 멀티 심볼일 때 구조가 다를 수 있어 안전 접근
                sub = df[code] if code in df.columns.get_level_values(0) else df
                closes = sub["Close"].dropna()
                if len(closes) == 0:
                    rows.append(Row(name, code, None, None))
                    continue
                last = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
                change_pct = None
                if prev and prev != 0:
                    change_pct = (last - prev) / prev * 100.0

                rows.append(Row(name=name, code=code, price=last, change_pct=change_pct))
            except Exception:
                rows.append(Row(name, code, None, None))
        return rows
