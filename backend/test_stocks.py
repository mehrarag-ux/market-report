"""
Smoke test: validates Twelve Data + FRED fetch for all tickers.
Run from backend/: python td_smoke_test.py
Stops before any LLM call.
"""

import os, sys
from dotenv import load_dotenv

load_dotenv()

td_key = os.getenv("TWELVEDATA_API_KEY", "")
fred_key = os.getenv("FRED_API_KEY", "")

print("=" * 60)
print(f"TWELVEDATA_API_KEY : {'SET' if td_key else 'MISSING'}")
print(f"FRED_API_KEY       : {'SET' if fred_key else 'MISSING'}")
print()

from config import WATCHLIST_AI, STW_POOL, all_tickers
from data import fetch_closes, metrics_for, beta_vs_market, FRED_MAP

QUANTUM = ["IONQ", "QUBT", "RGTI", "ARQQ", "GFS", "QTUM"]

all_syms = all_tickers()
td_syms  = [t for t in all_syms if t not in FRED_MAP]
n_chunks = (len(td_syms) + 7) // 8

print(f"Total tickers : {len(all_syms)}")
print(f"Via TD        : {len(td_syms)} in {n_chunks} chunks (~{(n_chunks-1)*61}s wait)")
print(f"Via FRED      : {list(FRED_MAP.keys())}")
print()
print(f"Quantum tickers: {QUANTUM}")
print()

print("Fetching...")
try:
    closes = fetch_closes(period_days=365)
except Exception as e:
    print(f"FATAL: {e}")
    sys.exit(1)

print(f"\nShape: {closes.shape}  |  {closes.index[0].date()} -> {closes.index[-1].date()}\n")

passed, failed, partial = [], [], []

for sym in all_syms:
    if sym not in closes.columns:
        failed.append(sym)
        continue
    col = closes[sym].dropna()
    row = (sym, len(col), round(float(col.iloc[-1]), 4) if len(col) else None, col.index[-1].date() if len(col) else None)
    (partial if len(col) < 50 else passed).append(row)

print("PASSED:")
for sym, n, val, dt in passed:
    print(f"  {sym:<8} {n:4d} days  last={val} on {dt}")

if partial:
    print("\nPARTIAL (<50 days):")
    for sym, n, val, dt in partial:
        print(f"  {sym:<8} {n:4d} days  last={val} on {dt}")

if failed:
    print("\nFAILED (not returned by TD):")
    for sym in failed:
        print(f"  {sym:<8} -- remove from config")

# Quantum-specific check
print("\nQUANTUM SUMMARY:")
all_results = {r[0]: r for r in passed + partial}
for t in QUANTUM:
    if t in failed:
        print(f"  {t:<8} FAILED -- remove from config")
    elif t in all_results:
        sym, n, val, dt = all_results[t]
        flag = " (partial)" if t in [r[0] for r in partial] else ""
        print(f"  {t:<8} ok  {n} days  last={val}{flag}")
    else:
        print(f"  {t:<8} not in config")

# Metrics sanity on quantum
if "SPY" in closes:
    print("\nMETRICS (quantum tickers):")
    for t in QUANTUM:
        if t in closes.columns:
            m = metrics_for(closes[t])
            b = beta_vs_market(closes[t], closes["SPY"])
            print(f"  {t:<8} price={m.get('price')}  day={m.get('day_change')}%  beta={b}  var95={m.get('var95_pct')}%")

print("\n" + "=" * 60)