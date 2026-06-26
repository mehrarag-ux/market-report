"""
Static configuration only. No logic, no fetching.
NOTE: INDICES use ETF proxies (SPY/QQQ) — Twelve Data free tier does not
support raw index symbols (^GSPC, ^NDX).
VIX fetched via Twelve Data. 10Y yield via FRED.
"""

import os

BASE_DIR    = os.path.dirname(__file__)
LOG_DIR     = os.path.join(BASE_DIR, "logs")
REPORTS_DIR = os.path.join(BASE_DIR, "..", "frontend", "reports")

CONFIG = {
    "to_emails": [
        "mehrarag@gmail.com",
        "pranav2vis@gmail.com",
        "khyatibgupta234@gmail.com",
        "bharatdgupta@gmail.com",
        "mmohnot@gmail.com"
    ],
    "from_name":    "Daily Market Report",
    "claude_model": "claude-sonnet-4-6",
    "max_tokens":   20000,
    "var_position": 10000,
}

INDICES = {
    "SPY":  "S&P 500 (SPY)",
    "QQQ":  "Nasdaq 100 (QQQ)",
    "^VIX": "VIX",
}
TNX = "^TNX"

# SPOTLIGHTS: earnings date tracking only — Section 2 removed
SPOTLIGHTS = [
    {"symbol": "MU", "name": "Micron Technology"},
]

WATCHLIST_AI = [
    {"symbol": "MU",    "name": "Micron Technology"},
    {"symbol": "SPCX",  "name": "SpaceX"},
    {"symbol": "NVDA",  "name": "Nvidia"},
    {"symbol": "AMD",   "name": "AMD"},
    {"symbol": "AVGO",  "name": "Broadcom"},
    {"symbol": "GOOGL", "name": "Alphabet"},
    {"symbol": "IBM",   "name": "IBM"},
    {"symbol": "MSFT",  "name": "Microsoft"},
    {"symbol": "INTC",  "name": "Intel"},
    {"symbol": "C",     "name": "Citigroup"},
    {"symbol": "QRVO",  "name": "Qorvo"},
    {"symbol": "ANET",  "name": "Arista Networks"},
    {"symbol": "WQTM",  "name": "Quantum ETF (WQTM)"},
    {"symbol": "GFS",   "name": "GlobalFoundries"},
]

STW_POOL = [
    "SPCX","MSFT","GOOGL","NVDA","AMD","AVGO","IBM",
    "C","MU","QRVO","ANET",
    "IONQ","QUBT","RGTI","ARQQ","GFS","QTUM",
]

SECTOR_ETFS = {
    "XLK":  "Technology",
    "XLF":  "Financials",
    "XLE":  "Energy",
    "XLV":  "Health Care",
    "XLY":  "Consumer Disc",
    "XLP":  "Consumer Staples",
    "XLI":  "Industrials",
    "XLB":  "Materials",
    "XLU":  "Utilities",
    "XLRE": "Real Estate",
    "XLC":  "Communications",
}


def all_tickers():
    """Every equity/ETF/index symbol needing price history, deduped.
    ^VIX via Twelve Data alias. ^TNX via FRED. Macro series fetched separately."""
    syms  = [s for s in INDICES if not s.startswith("^")]
    syms += [TNX]
    syms += ["^VIX"]
    syms += [s["symbol"] for s in WATCHLIST_AI]
    syms += list(SECTOR_ETFS)
    syms += STW_POOL
    return sorted(set(syms))