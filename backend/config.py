"""
Static configuration only. No logic, no fetching.
NOTE: INDICES use ETF proxies (SPY/QQQ/IWM) — Twelve Data free tier does not
support raw index symbols (^GSPC, ^NDX, ^RUT).
VIX and 10Y yield are fetched from FRED — kept as ^VIX / ^TNX internally.
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
    ],
    "from_name":    "Daily Market Report",
    "claude_model": "claude-sonnet-4-6",
    "max_tokens":   16000,
    "var_position": 10000,  # $ basis for VaR dollar figures
}

# --- Index proxies ---------------------------------------------------------
# Twelve Data free tier doesn't serve raw index symbols.
# VIX + TNX sourced from FRED (see data.py FRED_MAP).
INDICES = {
    "SPY":  "S&P 500 (SPY)",
    "QQQ":  "Nasdaq 100 (QQQ)",
    "IWM":  "Russell 2000 (IWM)",
    "^VIX": "VIX",
}
TNX = "^TNX"  # 10-year Treasury yield — fetched from FRED

# Spotlight deep-dive stocks (full table + verdict + risk box)
SPOTLIGHTS = [
    {"symbol": "C",    "name": "Citigroup"},
    {"symbol": "QRVO", "name": "Qorvo"},
    {"symbol": "MU",   "name": "Micron Technology"},
]

# AI / Mag7 watchlist
WATCHLIST_AI = [
    {"symbol": "NVDA",  "name": "Nvidia"},
    {"symbol": "AMD",   "name": "AMD"},
    {"symbol": "AVGO",  "name": "Broadcom"},
    {"symbol": "GOOGL", "name": "Alphabet"},
    {"symbol": "IBM",   "name": "IBM"},
    {"symbol": "MSFT",  "name": "Microsoft"},
]

# Stocks-to-watch candidate pool (LLM picks 5)
STW_POOL = [
    "MSFT", "GOOGL", "NVDA",
    "AMD",  "AVGO",  "IBM",
    "QRVO", "C",     "MU",
]

# SPDR sector ETFs
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

# Consumer confidence — set manually each week.
# One of: "rising", "stable", "falling", "sharply_falling" — or None for N/A
CONSUMER_CONFIDENCE = None


def all_tickers():
    """Every symbol needing price history, deduped.
    ^VIX and ^TNX excluded here — fetched from FRED in data.py."""
    syms  = [s for s in INDICES if not s.startswith("^")]  # SPY, QQQ, IWM
    syms += [TNX]                                           # ^TNX for FRED
    syms += ["^VIX"]                                        # ^VIX for FRED
    syms += [s["symbol"] for s in SPOTLIGHTS]
    syms += [s["symbol"] for s in WATCHLIST_AI]
    syms += list(SECTOR_ETFS)
    syms += STW_POOL
    return sorted(set(syms))