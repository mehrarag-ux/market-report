"""
ONE narrative prompt. LLM receives REAL numbers and returns ONLY JSON narrative.
web_search on for news, analyst targets, earnings, opportunity scanning,
market trends, portfolio allocation, sector opportunity radar.
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
  "sector_opportunity_radar": {
    "macro_context": "2-3 sentences framing today's macro opportunity environment. Reference specific verified data points: VIX level, 2Y/10Y spread (inverted/normal), SOFR vs Fed Funds, DXY trend. Answer: which macro conditions are opening or closing sector-level opportunities right now?",
    "themes": [
      {
        "sector": "GICS sector name e.g. Technology / Financials / Health Care",
        "theme": "descriptive theme name e.g. 'Domestic Chip Renaissance'",
        "opportunity_driver": "2-3 specific catalysts active today or in next 30 days with at least one data point",
        "conviction": "HIGH|MEDIUM|LOW",
        "time_horizon": "Tactical (1-3 months)|Structural (12+ months)|Tactical + Structural",
        "illustrative_names": "2-3 company names each followed by one phrase explaining HOW they embody the sector theme — framed as illustrative of the opportunity set, not standalone picks"
      }
    ],
    "deep_dives": [
      {
        "sector": "sector name",
        "snapshot": "Forward P/E vs 10-year sector average, YTD sector ETF return, fund flow direction",
        "why_today": "2-3 sentences on specific catalysts from current session or next 7-day calendar",
        "sub_industries": [
          {
            "name": "sub-industry name",
            "conviction": "Highest|High|Medium-High|Medium",
            "rationale": "one sentence on why this sub-industry leads within the broader sector theme",
            "illustrative": "1-2 company names each with one sentence connecting to the sub-industry and broader sector theme"
          }
        ],
        "key_risk": "one specific risk that would invalidate the entire sector thesis, with one supporting data point"
      }
    ]
  },
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
        "ai_rows":                 data["ai_rows"],
        "sectors_up":              data["winners"],
        "sectors_down":            data["losers"],
        "early_warning":           data["early_warning"],
        "macro_indicators":        data.get("macro", {}),
        "illustrative_candidates": data["candidate_data"],
    }

    known_tickers = (
        [s["ticker"] for s in data["spotlights"]]
        + [r["ticker"] for r in data["ai_rows"]]
    )

    return f"""You are a US stock market portfolio manager writing a daily briefing for overseas retail investors.

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

5. SECTOR OPPORTUNITY RADAR (Section 7)
   Search: "best performing sectors today {mkt['month_year']}"
   Search: "sector rotation fund flows {mkt['month_year']}"
   Search: "Nasdaq 100 sector themes investment catalysts {mkt['month_year']}"

   Identify 3-5 dominant investment themes active today across GICS sectors.
   For the top 2 highest-conviction sectors produce structured sub-industry deep dives.

   CRITICAL CONSTRAINT: SECTOR-FIRST, not stock-first.
   - Every company mention must appear within a sentence explicitly connecting it to the wider sector or thematic trend
   - Never frame any company as a standalone buy/sell recommendation
   - Use companies ONLY as illustrative examples embodying a broader sector thesis
   - PROHIBITED language: "buy", "sell", "recommend", "price target", "top pick"
   - REQUIRED language: "opportunity set", "positioned to benefit", "thematic exposure", "illustrative of the trend", "representative of the sub-industry"

6. MARKET TRENDS (Section 8)
   Search: "S&P 500 Nasdaq most active stocks today {mkt['month_year']}"
   and: "US market trend signals upside downside risk {mkt['month_year']}"
   Provide 2-3 sentence commentary + 3 upside risks + 3 downside risks each with one data point.

7. PORTFOLIO ALLOCATION (Section 9)
   Search: "portfolio allocation retirement 5-8 years capital growth preservation {mkt['month_year']}"
   Build allocation for an experienced professional retiring in 5-8 years.
   Profile: capital growth with increasing capital preservation, risk-aware.
   - 5-7 buckets with allocation % and purpose (must sum to 100%)
   - Adjust based on current VIX and macro_indicators in verified data above
   - Include a rebalance_trigger: specific market condition warranting rebalancing

VERDICT RULES FOR SPOTLIGHTS (BUY/HOLD/SELL):
- Reference P/E, price vs 52W high/low, 1-year momentum, beta, AND analyst consensus target
- Stock above analyst consensus target -> lean SELL or HOLD
- Stock below analyst consensus target -> lean BUY or HOLD
- High beta (>2) warrants explicit risk mention

NEVER use web_search to override any verified number (price, beta, VaR, returns).

Return ONLY valid JSON matching this schema. No markdown fences, no prose outside JSON:
{NARRATIVE_SCHEMA}"""