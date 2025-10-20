import requests, datetime as dt

KEY = "YOUR_KEY1"
SECRET = "YOUR_SECRET"
BASE = "https://data.alpaca.markets/v2"

headers = {
    "APCA-API-KEY-ID": "PK7VDBLGNZWB6W351ME3",
    "APCA-API-SECRET-KEY": "CWIsbeLyjvQu3aFglp4YOO9iZjgjkmtNwCL1Svac"
}
params = {
    "timeframe": "1Min",
    "start": "2025-10-08T00:00:00Z",
    "end":   "2025-10-09T23:59:59Z",
    "limit": 300,
    "feed": "iex",
    "adjustment": "raw"
}

r = requests.get(f"{BASE}/stocks/QQQ/bars", headers=headers, params=params)
r.raise_for_status()
data = r.json() or {}
bars = data.get("bars") or []     # ← None 방어

rows = []
for b in bars:
    # b["t"]는 ISO8601 문자열 (예: "2025-10-10T13:31:00Z")
    ts = int(dt.datetime.fromisoformat(b["t"].replace("Z","+00:00")).timestamp() * 1000)
    rows.append({
        "t": ts,
        "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"],
        "v": b.get("v", 0),
        "n": b.get("n", 0)
    })

print(len(rows), "bars ready for charts.py")
