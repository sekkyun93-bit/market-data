"""Fetch market data from Yahoo Finance for the morning brief.

Writes data/latest.json with:
  intraday  - last regular US session, 5-minute bars (cash indices)
  futures   - last ~24h of 5-minute bars (index futures)
  daily     - ~3 months of daily closes (Korea, US, macro)
  weekly    - last 5 sessions of 30-minute bars (cash indices)
"""
import json
import time
import datetime as dt
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
HOSTS = ["https://query2.finance.yahoo.com", "https://query1.finance.yahoo.com"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}

INTRADAY = ["^GSPC", "^IXIC", "^DJI", "^RUT", "^SOX"]
FUTURES = ["NQ=F", "ES=F"]
DAILY = ["^GSPC", "^IXIC", "^DJI", "^RUT", "^SOX", "^VIX", "^TNX",
         "^KS11", "^KQ11", "005930.KS", "000660.KS", "KRW=X",
         "NQ=F", "ES=F", "CL=F", "BZ=F", "GC=F", "BTC-USD", "DX-Y.NYB"]


def chart(symbol, **params):
    last_err = None
    for attempt in range(3):
        for host in HOSTS:
            try:
                r = requests.get(f"{host}/v8/finance/chart/{requests.utils.quote(symbol)}",
                                 params=params, headers=HEADERS, timeout=20)
                if r.status_code == 200:
                    res = r.json()["chart"]["result"]
                    if res:
                        return res[0]
                last_err = f"HTTP {r.status_code}"
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"{symbol}: {last_err}")


def series(res, keep=None):
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(ts):
        c = q["close"][i]
        if c is None:
            continue
        if keep and not keep(t):
            continue
        rows.append([t, round(c, 4),
                     round(q["low"][i], 4) if q["low"][i] is not None else None,
                     round(q["high"][i], 4) if q["high"][i] is not None else None])
    m = res["meta"]
    return {
        "prevClose": m.get("chartPreviousClose"),
        "regularMarketPrice": m.get("regularMarketPrice"),
        "regularMarketTime": m.get("regularMarketTime"),
        "currency": m.get("currency"),
        "cols": ["t", "close", "low", "high"],
        "rows": rows,
    }


def main():
    now = dt.datetime.now(dt.timezone.utc)
    out = {"fetched_at_utc": now.isoformat(timespec="seconds"),
           "fetched_at_kst": now.astimezone(KST).isoformat(timespec="seconds"),
           "source": "Yahoo Finance chart API",
           "intraday": {}, "futures": {}, "daily": {}, "weekly": {}, "errors": {}}

    for s in INTRADAY:
        try:
            res = chart(s, interval="5m", range="5d")
            ts = [t for t in (res.get("timestamp") or [])]
            if not ts:
                raise RuntimeError("no data")
            last_day = dt.datetime.fromtimestamp(ts[-1], ET).date()
            keep = lambda t, d=last_day: dt.datetime.fromtimestamp(t, ET).date() == d
            ser = series(res, keep)
            # previous close = last close of the prior session in the same response
            prior = [t for t in ts if dt.datetime.fromtimestamp(t, ET).date() < last_day]
            if prior:
                q = res["indicators"]["quote"][0]
                idx = max(i for i, t in enumerate(ts) if t in set(prior) and q["close"][i] is not None)
                ser["prevClose"] = round(q["close"][idx], 4)
            ser["session_date_et"] = last_day.isoformat()
            out["intraday"][s] = ser
        except Exception as e:  # noqa: BLE001
            out["errors"][f"intraday {s}"] = str(e)

    for s in FUTURES:
        try:
            res = chart(s, interval="5m", range="2d", includePrePost="true")
            cutoff = now.timestamp() - 26 * 3600
            out["futures"][s] = series(res, lambda t: t >= cutoff)
        except Exception as e:  # noqa: BLE001
            out["errors"][f"futures {s}"] = str(e)

    for s in DAILY:
        try:
            out["daily"][s] = series(chart(s, interval="1d", range="3mo"))
        except Exception as e:  # noqa: BLE001
            out["errors"][f"daily {s}"] = str(e)

    for s in INTRADAY:
        try:
            out["weekly"][s] = series(chart(s, interval="30m", range="5d"))
        except Exception as e:  # noqa: BLE001
            out["errors"][f"weekly {s}"] = str(e)

    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    ok = sum(len(out[k]) for k in ("intraday", "futures", "daily", "weekly"))
    print(f"saved {ok} series, {len(out['errors'])} errors")
    for k, v in out["errors"].items():
        print("ERR", k, v)
    if ok == 0:
        raise SystemExit("no data fetched")


if __name__ == "__main__":
    main()
