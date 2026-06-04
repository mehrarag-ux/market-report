"""
ONE narrative prompt. LLM receives REAL numbers and returns ONLY JSON narrative.
web_search is on for news, analyst targets, earnings, opportunity scanning,
market trends, and portfolio allocation.
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
  "stw": [{"ticker":"X","rating":"BUY|HOLD|SELL","horizon":"5-YEAR|1-YEAR|EXIT NOW","reason":"2 sentences: catalyst + action","price_note":"current price if not in our verified data"}],
  "market_trends": {
    "commentary": "2-3 sentences on what today's market action reveals about near-term direction",
    "upside_risks": ["specific upside risk with one data point","upside risk 2","upside risk 3"],
    "downside_risks": ["specific downside risk with one data point","downside risk 2","downside risk 3"]
  },
  "portfolio_allocation": {
    "rationale": "2 sentences: current market context justifying this allocation for a 5-8 year retirement horizon",
    "buckets": [
      {"bucket": "bucket name", "allocation_pct": 0, "purpose": "purpose description"}
    ],
    "rebalance_trigger": "specific market condition or threshold that should prompt rebalancing"
  }
}"""


def narrative_prompt(mkt: dict, data: dict) -> str:
    nums = {
        "indices": data["indices"],
        "spotlights": [
            {k: s[k] for k in ("ticker","name","price","day_change","y1","hi52","lo52","pe","div","beta","target") if k in s}
            for s in data["spotlights"]
        ],
        "ai_rows":        data["ai_rows"],
        "sectors_up":     data["winners"],
        "sectors_down":   data["losers"],
        "early_warning":  data["early_warning"],
        "stw_candidates": data["stw_data"],
    }

    known_tickers = (
        [s["ticker"] for s in data["spotlights"]]
        + [r["ticker"] for r in data["ai_rows"]]
    )

    return f"""You are a US stock market portfolio manager writing a daily briefing for a retail investor based in Singapore.

{mkt['context']}

These numbers are VERIFIED FACTS from our data layer. Do NOT change any number.
Do NOT invent prices. Reason ONLY over these verified numbers:

{json.dumps(nums, indent=2, default=str)}

WEB SEARCH INSTRUCTIONS — use web_search for ALL of the following:

1. NEWS & CATALYSTS
   Search for today's main US market drivers, individual stock news, Fed commentary.

2. SPOTLIGHT ANALYST TARGETS
   For each spotlight ticker {[s["ticker"] for s in data["spotlights"]]}, search:
   "[TICKER] analyst price target consensus 2026"
   Return as "$XXX (source, month year)". Overrides stale yfinance target above.

3. EARNINGS CALENDAR
   Search: "Nasdaq 100 NDX earnings calendar next 2 weeks {mkt['month_year']}"
   Return 8-12 upcoming dates across full NDX. Format: company, ticker, date.
   Include known tickers {known_tickers} even if already have verified dates.

4. OPPORTUNITY RADAR
   Search: "Nasdaq 100 best opportunities undervalued stocks {mkt['month_year']}"
   and: "NDX sector rotation catalyst {mkt['month_year']}"
   Identify 3 themes from full NDX composite. Each needs one data point + one example ticker.

5. STOCKS TO WATCH
   Search: "Nasdaq 100 stocks to watch this week {mkt['month_year']}"
   and: "NDX top movers analyst upgrades {mkt['month_year']}"
   Pick exactly 5 stocks from anywhere in NDX. Include price_note for any not in stw_candidates.
   Must include: 1x BUY 5-YEAR, 1x HOLD 1-YEAR, 1x SELL EXIT NOW.

6. MARKET TRENDS (Section 8)
   Search: "S&P 500 Nasdaq most active stocks today {mkt['month_year']}"
   and: "US market trend signals upside downside risk {mkt['month_year']}"
   Based on today's most active stocks and market action, provide:
   - 2-3 sentence commentary on what today's action reveals about near-term direction
   - 3 specific upside risks, each with one data point
   - 3 specific downside risks, each with one data point

7. PORTFOLIO ALLOCATION (Section 9)
   Search: "portfolio allocation retirement 5-8 years capital growth preservation {mkt['month_year']}"
   Build an allocation for an experienced professional retiring in 5-8 years.
   Profile: capital growth with increasing capital preservation, risk-aware.
   - Provide 5-7 buckets in table format with allocation % and purpose
   - Total allocation must sum to 100%
   - Include a rebalance_trigger: a specific market condition that warrants rebalancing
   - Adjust the allocation based on current VIX={data['early_warning'].get('signals',[])} and market conditions

VERDICT RULES (BUY/HOLD/SELL):
- Reference P/E, price vs 52W high/low, 1-year momentum, beta, AND analyst consensus target
- Stock above analyst consensus target → lean SELL or HOLD
- Stock below analyst consensus target → lean BUY or HOLD
- High beta (>2) warrants explicit risk mention

NEVER use web_search to override any verified number (price, beta, VaR, returns).

Return ONLY valid JSON matching this schema. No markdown fences, no prose outside JSON:
{NARRATIVE_SCHEMA}"""