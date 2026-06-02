"""
ONE narrative prompt. The LLM receives REAL numbers and returns ONLY JSON
narrative — it never invents a price. web_search is on for news, analyst
targets, broader NDX earnings, and opportunity scanning.
"""

import json

NARRATIVE_SCHEMA = """{
  "pulse": "2 sentences summarising the session. Must reference 'Nasdaq 100 (NDX)'.",
  "spotlights": {
    "<TICKER>": {
      "rating": "BUY|HOLD|SELL",
      "verdict": "3 sentences: valuation vs analyst target, momentum, key risk",
      "business_risk": "single biggest risk with one specific number",
      "analyst_target": "search '[TICKER] analyst price target consensus 2026' — return as '$XXX (source, month year)' or 'N/A'"
    }
  },
  "why_paras": ["para: what happened","para: why","para: what it means for investors"],
  "macro": ["plain-English macro point 1","point 2","point 3"],
  "earnings_calendar": [
    {"company": "Company Name", "ticker": "TICK", "date": "Mon DD, YYYY"}
  ],
  "opportunity_radar": [{"theme":"name","why":"why NOW + one data point","example":"TICKER"}],
  "portfolio_direction": "1 paragraph: buy / hold / reduce risk, justified by VIX, valuations, macro.",
  "stw": [{"ticker":"X","rating":"BUY|HOLD|SELL","horizon":"5-YEAR|1-YEAR|EXIT NOW","reason":"2 sentences: catalyst + action","price_note":"current price if not in our verified data"}]
}"""


def narrative_prompt(mkt: dict, data: dict) -> str:
    nums = {
        "indices": data["indices"],
        "spotlights": [
            {
                k: s[k]
                for k in (
                    "ticker", "name", "price", "day_change",
                    "y1", "hi52", "lo52", "pe", "div", "beta", "target",
                )
                if k in s
            }
            for s in data["spotlights"]
        ],
        "ai_rows":        data["ai_rows"],
        "sectors_up":     data["winners"],
        "sectors_down":   data["losers"],
        "early_warning":  data["early_warning"],
        "stw_candidates": data["stw_data"],
    }

    # Flatten all tickers we already have verified data for
    known_tickers = (
        [s["ticker"] for s in data["spotlights"]]
        + [r["ticker"] for r in data["ai_rows"]]
    )

    return f"""You are a US stock market portfolio manager writing a daily briefing for a retail investor based in Singapore.

{mkt['context']}

These numbers are VERIFIED FACTS from our data layer. Do NOT change any number.
Do NOT invent prices. Reason ONLY over these verified numbers:

{json.dumps(nums, indent=2, default=str)}

─────────────────────────────────────────────
WEB SEARCH INSTRUCTIONS — use web_search for ALL of the following:
─────────────────────────────────────────────

1. NEWS & CATALYSTS
   Search for today's main US market drivers, individual stock news, Fed commentary.

2. SPOTLIGHT ANALYST TARGETS
   For each spotlight ticker {[s["ticker"] for s in data["spotlights"]]}, search:
   "[TICKER] analyst price target consensus 2026"
   Return result in analyst_target as "$XXX (source, month year)".
   Your web search result takes precedence over the stale yfinance 'target' above.

3. EARNINGS CALENDAR — search broadly across Nasdaq 100
   Search: "Nasdaq 100 NDX earnings calendar next 2 weeks {mkt['month_year']}"
   Return 8–12 upcoming earnings dates covering the full NDX, not just our watchlist.
   Format each as: company, ticker, date.
   Our known tickers {known_tickers} may already have verified dates — still include them.

4. OPPORTUNITY RADAR — scan full Nasdaq 100
   Search: "Nasdaq 100 best opportunities undervalued stocks {mkt['month_year']}"
   and: "NDX sector rotation catalyst {mkt['month_year']}"
   Identify 3 themes/opportunities from across the full NDX composite — not limited
   to our 13 watchlist stocks. Each theme needs one specific data point and one
   example ticker (can be any NDX constituent, not just our watchlist).

5. STOCKS TO WATCH — scan full Nasdaq 100
   Search: "Nasdaq 100 stocks to watch this week {mkt['month_year']}"
   and: "NDX top movers analyst upgrades {mkt['month_year']}"
   Pick exactly 5 stocks from anywhere in the Nasdaq 100 composite.
   For any ticker NOT in our verified stw_candidates above, include the current
   price in price_note field.
   Must include at least:
   - 1 × BUY with horizon 5-YEAR
   - 1 × HOLD with horizon 1-YEAR
   - 1 × SELL with horizon EXIT NOW

─────────────────────────────────────────────
VERDICT RULES (BUY/HOLD/SELL) — must cite actual numbers:
─────────────────────────────────────────────
- Reference P/E, price vs 52W high/low, 1-year momentum, beta, AND analyst consensus target
- Stock trading meaningfully above analyst consensus target → lean SELL or HOLD
- Stock trading meaningfully below analyst consensus target → lean BUY or HOLD
- High beta (>2) warrants explicit risk mention in verdict

NEVER use web_search to override any verified number above (price, beta, VaR, returns).

Return ONLY valid JSON matching this schema. No markdown fences, no prose outside JSON:
{NARRATIVE_SCHEMA}"""