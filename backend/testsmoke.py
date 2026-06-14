"""
Smoke test: date logic + Twelve Data ticker validation.
Run as: python backend/testsmoke.py
"""

import datetime, os, sys, requests
from zoneinfo import ZoneInfo
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import pandas_market_calendars as mcal

UTC = ZoneInfo("UTC")
SGT = ZoneInfo("Asia/Singapore")
ET  = ZoneInfo("America/New_York")
TD_BASE = "https://api.twelvedata.com"

SECTION = lambda s: print(f"\n{'='*55}\n{s}\n{'='*55}")


def show_clocks():
    SECTION("CLOCKS")
    now_utc = datetime.datetime.now(UTC)
    now_sgt = now_utc.astimezone(SGT)
    now_et  = now_utc.astimezone(ET)
    print("UTC :", now_utc.strftime("%Y-%m-%d %H:%M:%S %a"))
    print("SGT :", now_sgt.strftime("%Y-%m-%d %H:%M:%S %a"))
    print("ET  :", now_et.strftime("%Y-%m-%d %H:%M:%S %a"))
    print("date.today() on this runner :", datetime.date.today())


def show_nyse_schedule(today: datetime.date):
    SECTION("NYSE SCHEDULE")
    nyse  = mcal.get_calendar("NYSE")
    sched = nyse.schedule(
        start_date=(today - datetime.timedelta(days=10)).isoformat(),
        end_date=today.isoformat(),
    )
    print(sched[["market_open", "market_close"]])
    return sched


def check_date_logic(today: datetime.date, sched):
    SECTION("DATE LOGIC")
    days = [d.date() for d in sched.index]

    if today in days:
        old_open, old_ltd = True, today
    else:
        past = [d for d in days if d < today]
        old_open, old_ltd = False, (past[-1] if past else today - datetime.timedelta(days=1))

    past = [d for d in days if d < today]
    new_ltd = past[-1] if past else today - datetime.timedelta(days=1)

    print(f"OLD logic -> market_open={old_open}, last_trading_day={old_ltd}")
    print(f"NEW logic -> market_open=False,  last_trading_day={new_ltd}")
    if old_ltd != new_ltd:
        print(f"  MISMATCH DETECTED: old={old_ltd} vs new={new_ltd} -- fix is needed")
    else:
        print("  Both agree -- no date mismatch today")
    return new_ltd


def check_ticker(sym: str, td_key: str, start: datetime.date, end: datetime.date):
    try:
        r = requests.get(
            f"{TD_BASE}/time_series",
            params={
                "symbol": sym, "interval": "1day",
                "start_date": start.isoformat(), "end_date": end.isoformat(),
                "outputsize": 10, "apikey": td_key, "format": "JSON",
            },
            timeout=15,
        )
        j = r.json()
        if isinstance(j, dict) and j.get("status") == "error":
            return None, f"TD ERROR: {j.get('message','')}"
        values = j.get("values", [])
        if not values:
            return None, "NO VALUES RETURNED"
        latest = float(values[0]["close"])
        return latest, "OK"
    except Exception as e:
        return None, f"EXCEPTION: {e}"


def check_tickers(new_ltd: datetime.date):
    SECTION("TICKER SPOT-CHECKS (Twelve Data)")
    td_key = os.getenv("TWELVEDATA_API_KEY", "")
    if not td_key:
        print("TWELVEDATA_API_KEY not set -- skipping ticker checks")
        print("Check that .env exists in backend/ and contains TWELVEDATA_API_KEY=...")
        return

    print(f"API key loaded: {td_key[:6]}...{td_key[-4:]}")
    start = new_ltd - datetime.timedelta(days=5)
    end   = new_ltd

    checks = [
        ("SPCX",  "SpaceX IPO Jun 12 2026 -- old ProShares ETF was ~$22, now should be ~$135-165"),
        ("SPY",   "Control: S&P 500 ETF"),
        ("NVDA",  "Control: Nvidia"),
        ("QQQ",   "Control: Nasdaq 100 ETF"),
    ]

    for sym, note in checks:
        price, status = check_ticker(sym, td_key, start, end)
        flag = ""
        if sym == "SPCX" and price is not None:
            if price < 50:
                flag = "  *** STALE: old ETF price -- Twelve Data mapping lag, wait 1-2 days"
            else:
                flag = "  CORRECT: SpaceX IPO price"
        print(f"  {sym:8s} | {status:30s} | close={price} | {flag}")
        print(f"           | {note}")


def main():
    show_clocks()
    today = datetime.date.today()
    sched = show_nyse_schedule(today)
    new_ltd = check_date_logic(today, sched)
    check_tickers(new_ltd)
    print()


if __name__ == "__main__":
    main()