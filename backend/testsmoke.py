"""
Smoke test for date/market-context logic.
Run on GH Actions runner (or locally) to see what today/UTC/SGT/ET resolve to,
and what last_trading_day the current get_market_context logic would produce.
"""

import datetime
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal

UTC = ZoneInfo("UTC")
SGT = ZoneInfo("Asia/Singapore")
ET  = ZoneInfo("America/New_York")


def show_clocks():
    now_utc = datetime.datetime.now(UTC)
    now_sgt = now_utc.astimezone(SGT)
    now_et  = now_utc.astimezone(ET)
    print("UTC :", now_utc.strftime("%Y-%m-%d %H:%M:%S %a"))
    print("SGT :", now_sgt.strftime("%Y-%m-%d %H:%M:%S %a"))
    print("ET  :", now_et.strftime("%Y-%m-%d %H:%M:%S %a"))
    print()
    print("date.today() on this runner :", datetime.date.today())
    print()


def show_nyse_schedule(today: datetime.date):
    nyse  = mcal.get_calendar("NYSE")
    sched = nyse.schedule(
        start_date=(today - datetime.timedelta(days=10)).isoformat(),
        end_date=today.isoformat(),
    )
    print("NYSE schedule (last 10 days up to and incl today):")
    print(sched[["market_open", "market_close"]])
    print()
    return sched


def old_logic(today: datetime.date, sched):
    days = [d.date() for d in sched.index]
    if today in days:
        return True, today
    past = [d for d in days if d < today]
    return False, (past[-1] if past else today - datetime.timedelta(days=1))


def new_logic(today: datetime.date, sched):
    days = [d.date() for d in sched.index]
    past = [d for d in days if d < today]
    ltd  = past[-1] if past else today - datetime.timedelta(days=1)
    return False, ltd


def main():
    show_clocks()
    today = datetime.date.today()
    sched = show_nyse_schedule(today)

    open_old, ltd_old = old_logic(today, sched)
    open_new, ltd_new = new_logic(today, sched)

    print(f"OLD logic -> market_open={open_old}, last_trading_day={ltd_old}")
    print(f"NEW logic -> market_open={open_new}, last_trading_day={ltd_new}")


if __name__ == "__main__":
    main()