# adapters/kiwoom.py
"""
Kiwoom OpenAPI+ (모의투자/실계좌 공용) 어댑터
- Windows 전용 (OCX/COM), 키움증권 HTS 설치 및 로그인 필요
- PyQt 이벤트 루프와 충돌하지 않도록, block_request 기반으로 단발 조회만 사용
- 실시간은 OnReceiveRealData 바인딩으로 확장 가능
"""
import time
from typing import List, Tuple
from .base import MarketDataSource, Bar
try:
    from pykiwoom.kiwoom import Kiwoom
except Exception as e:
    Kiwoom = None

class KiwoomSource(MarketDataSource):
    def __init__(self):
        if Kiwoom is None:
            raise RuntimeError("pykiwoom 미설치 또는 Windows/COM 환경 아님. 'pip install pykiwoom' 및 Windows에서 실행하세요.")
        self.kiwoom = Kiwoom()
        ret = self.kiwoom.CommConnect(block=True)
        if ret != 0:
            raise RuntimeError(f"Kiwoom 로그인 실패(ret={ret})")

    @staticmethod
    def _code_fix(symbol: str) -> str:
        s = symbol.strip()
        if len(s) < 6:
            s = s.zfill(6)
        return s

    def get_recent_bars(self, symbol: str, timeframe: str, limit: int) -> List[Bar]:
        code = self._code_fix(symbol)
        tf = timeframe.lower()
        if tf.endswith("d"):
            return self._req_opt10081_daily(code, limit)
        else:
            unit_map = {"1m":"1","3m":"3","5m":"5","10m":"10","15m":"15","30m":"30","60m":"60"}
            unit = unit_map.get(tf, "1")
            return self._req_opt10080_minute(code, unit, limit)

    def get_last_trade(self, symbol: str) -> Tuple[int, float, int]:
        code = self._code_fix(symbol)
        df = self.kiwoom.block_request(
            "opt10001",
            종목코드=code,
            output="주식기본정보",
            next=0
        )
        if df is None or len(df) == 0:
            raise RuntimeError("opt10001 응답 없음")
        row = df.iloc[0]
        try:
            price = float(str(row["현재가"]).replace(",", "").replace("+","" ).replace("-",""))
        except Exception:
            price = float(str(row.get("현재가", "0")).replace(",", "").replace("+","" ).replace("-",""))
        try:
            vol = int(str(row.get("누적거래량", "0")).replace(",", ""))
        except Exception:
            vol = 0
        ts = int(time.time())
        size = max(1, vol // 1000)
        return (ts, price, size)

    def _req_opt10080_minute(self, code: str, tick_unit: str, limit: int) -> List[Bar]:
        df = self.kiwoom.block_request(
            "opt10080",
            종목코드=code,
            틱범위=tick_unit,
            수정주가구분="1",
            output="주식분봉차트",
            next=0
        )
        if df is None or len(df) == 0:
            return []
        df = df.iloc[::-1].head(limit)
        bars: List[Bar] = []
        for _, r in df.iterrows():
            ymdhms = str(r.get("체결시간", ""))
            try:
                ts = int(time.mktime(time.strptime(ymdhms, "%Y%m%d%H%M%S")))
            except Exception:
                ts = int(time.time())
            o = float(str(r.get("시가","0")).replace(",","" ).replace("+","" ).replace("-",""))
            h = float(str(r.get("고가","0")).replace(",","" ).replace("+","" ).replace("-",""))
            l = float(str(r.get("저가","0")).replace(",","" ).replace("+","" ).replace("-",""))
            c = float(str(r.get("현재가","0")).replace(",","" ).replace("+","" ).replace("-",""))
            v = float(str(r.get("거래량","0")).replace(",","" ))
            bars.append(Bar(ts=ts, o=o, h=h, l=l, c=c, v=v))
        return bars

    def _req_opt10081_daily(self, code: str, limit: int) -> List[Bar]:
        from datetime import datetime
        today = datetime.now().strftime("%Y%m%d")
        df = self.kiwoom.block_request(
            "opt10081",
            종목코드=code,
            기준일자=today,
            수정주가구분="1",
            output="주식일봉차트조회",
            next=0
        )
        if df is None or len(df) == 0:
            return []
        df = df.iloc[::-1].head(limit)
        bars: List[Bar] = []
        for _, r in df.iterrows():
            ymd = str(r.get("일자", ""))
            try:
                ts = int(time.mktime(time.strptime(ymd + "000000", "%Y%m%d%H%M%S")))
            except Exception:
                ts = int(time.time())
            o = float(str(r.get("시가","0")).replace(",","" ).replace("+","" ).replace("-",""))
            h = float(str(r.get("고가","0")).replace(",","" ).replace("+","" ).replace("-",""))
            l = float(str(r.get("저가","0")).replace(",","" ).replace("+","" ).replace("-",""))
            c = float(str(r.get("현재가","0")).replace(",","" ).replace("+","" ).replace("-",""))
            v = float(str(r.get("거래량","0")).replace(",","" ))
            bars.append(Bar(ts=ts, o=o, h=h, l=l, c=c, v=v))
        return bars
