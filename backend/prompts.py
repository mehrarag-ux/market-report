"""
ONE narrative prompt. LLM receives REAL numbers and returns ONLY JSON narrative.
web_search on for news, earnings, opportunity scanning, sector radar,
risk heat map & market outlook, portfolio allocation.
Section 2 (Spotlights) removed — MU now in watchlist.
"""

import json

NARRATIVE_SCHEMA = """{
  "pulse": "2 sentences summarising the session. Must reference 'Nasdaq 100 (NDX)'.",
  "why_paras": ["para: what happened","para: why","para: what it means for investors"],
  "macro": ["plain-English macro point 1","point 2","point 3"],
  "earnings_calendar": [
    {"company": "Company Name", "ticker": "TICK", "date": "Mon DD, YYYY"}
  ],
  "opportunity_radar": [{"theme":"name","why":"why NOW + one data point","example":"TICKER"}],
  "portfolio_direction": "1 paragraph: buy / hold / reduce risk, justified by VIX, valuations, macro.",
  "sector_opportunity_radar": {
    "macro_context": "2-3 sentences framing today's macro opportunity environment. Reference specific verified data points: VIX level, 2Y/10Y spread (inverted/normal), SOFR vs Fed Funds, DXY trend.",
    "themes": [
      {
        "sector": "GICS sector name",
        "theme": "descriptive theme name",
        "opportunity_driver": "2-3 specific catalysts active today or in next 30 days with at least one data point",
        "conviction": "HIGH|MEDIUM|LOW",
        "time_horizon": "Tactical (1-3 months)|Structural (12+ months)|Tactical + Structural",
        "illustrative_names": "2-3 company names each followed by one phrase explaining HOW they embody the sector theme"
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
        "key_risk": "one specific risk that would invalidate the entire sector thesis with one supporting data point"
      }
    ]
  },
  "risk_heat_map_outlook": {
    "posture": "2-sentence market posture statement. Use precise language: SELECTIVE-RISK, RISK-ON, RISK-OFF, or NEUTRAL posture with specific justification.",
    "risk_heat_map": [
      {
        "sector": "GICS sector name",
        "macro_risk": "Low|Medium|High",
        "macro_note": "brief qualifier e.g. 'rate hike sensitivity'",
        "thematic_risk": "Low|Medium|High",
        "thematic_note": "e.g. 'AI monetization lag'",
        "geo_risk": "Low|Medium|High",
        "geo_note": "e.g. 'Taiwan dependency'",
        "valuation_risk": "Low|Medium|High",
        "valuation_note": "e.g. '40-53x P/E'",
        "overall_signal": "OVERWEIGHT|SELECTIVE|NEUTRAL|UNDERWEIGHT"
      }
    ],
    "catalysts_risks": [
      {
        "sector": "sector name",
        "catalysts": ["catalyst 1 with one data point", "catalyst 2 with one data point"],
        "risks": ["risk 1 with one data point", "risk 2 with one data point"],
        "illustrative_names": "ticker list — names appear as sector representatives, not standalone picks"
      }
    ],
    "catalyst_calendar": [
      {
        "date": "Mon DD",
        "event": "event name and ticker if earnings",
        "sectors_impacted": "impacted GICS sectors",
        "bull_scenario": "bullish outcome and sector implication",
        "bear_scenario": "bearish outcome and sector implication"
      }
    ],
    "scenarios": [
      {
        "scenario": "Bull Case|Base Case|Bear Case",
        "probability": "XX% — 3 scenarios must sum to 100%",
        "key_trigger": "specific event or condition triggering this scenario",
        "beneficiary_sectors": "sectors that outperform in this scenario",
        "vulnerable_sectors": "sectors that underperform in this scenario",
        "spy_implication": "SPY price range or directional target with basis"
      }
    ],
    "health_dashboard": [
      {
        "signal": "signal name",
        "reading": "current value with units",
        "status": "GREEN|AMBER|RED",
        "change": "vs prior session or prior week"
      }
    ]
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
        "indices":                 data["indices"],
        "ai_rows":                 data["ai_rows"],
        "sectors_up":              data["winners"],
        "sectors_down":            data["losers"],
        "early_warning":           data["early_warning"],
        "macro_indicators":        data.get("macro", {}),
        "illustrative_candidates": data["candidate_data"],
    }

    known_tickers = [r["ticker"] for r in data["ai_rows"]]

    return f"""You are a US stock market portfolio manager writing a daily briefing for overseas retail investors.

{mkt['context']}

These numbers are VERIFIED FACTS from our data layer. Do NOT change any number.
Do NOT invent prices. Reason ONLY over these verified numbers:

{json.dumps(nums, indent=2, default=str)}

WEB SEARCH INSTRUCTIONS — use web_search for ALL of the following:

1. NEWS & CATALYSTS
   Search for today's main US market drivers, individual stock news, Fed commentary.

2. EARNINGS CALENDAR
   Search: "Nasdaq 100 NDX earnings calendar next 2 weeks {mkt['month_year']}"
   Return 8-12 upcoming dates across full NDX. Format: company, ticker, date.
   Include known tickers {known_tickers} even if already have verified dates.

3. OPPORTUNITY RADAR
   Search: "Nasdaq 100 best opportunities undervalued stocks {mkt['month_year']}"
   and: "NDX sector rotation catalyst {mkt['month_year']}"
   Identify 3 themes from full NDX composite. Each needs one data point + one example ticker.

4. SECTOR OPPORTUNITY RADAR (Section 7)
   Search: "best performing sectors today {mkt['month_year']}"
   Search: "sector rotation fund flows {mkt['month_year']}"
   Search: "Nasdaq 100 sector themes investment catalysts {mkt['month_year']}"

   Identify 3-5 dominant investment themes active today across GICS sectors.
   For the top 2 highest-conviction sectors produce structured sub-industry deep dives.

   CRITICAL: SECTOR-FIRST, not stock-first.
   - Every company mention must appear within a sentence connecting it to the wider sector or thematic trend
   - Never frame any company as a standalone buy/sell recommendation
   - PROHIBITED: "buy", "sell", "recommend", "price target", "top pick"
   - REQUIRED: "opportunity set", "positioned to benefit", "thematic exposure", "illustrative of the trend"

5. RISK HEAT MAP & MARKET OUTLOOK (Section 8)
   CRITICAL: FORWARD-LOOKING ONLY. Do NOT summarise what happened today (covered in Sections 4 and 5).
   Answer: What risks and catalysts will drive sector performance over the next 1-30 trading days?

   Search: "sector risk outlook {mkt['month_year']}"
   Search: "HYG high yield credit spread current {mkt['month_year']}"
   Search: "economic calendar data releases next 2 weeks {mkt['month_year']}"
   Search: "NYSE advance decline line direction {mkt['month_year']}"

   STEP 2 — Score ALL 11 GICS sectors on these risk dimensions:
   - Macro Risk: Fed rate path sensitivity, GDP surprise risk, inflation exposure
   - Thematic Risk: AI disruption exposure, energy transition, regulatory risk
   - Geopolitical Risk: trade policy, commodity supply, foreign policy exposure
   - Valuation Risk: forward P/E vs 10-year sector average
   Overall Signal: OVERWEIGHT / SELECTIVE / NEUTRAL / UNDERWEIGHT

   STEP 3 — Top 5 most market-relevant sectors: upside catalysts vs downside risks table.
   Illustrative names appear in context of how catalyst/risk affects them as sector representatives.

   STEP 4 — 7-day catalyst calendar: earnings + economic releases + policy events.
   Include bull AND bear scenario for each event.

   STEP 5 — 3-Scenario Market Outlook: Bull / Base / Bear.
   Probabilities must sum to 100%. Include SPY price implication per scenario.

   STEP 6 — Market Health Dashboard. Use VERIFIED values from macro_indicators above:
   VIX={data.get('macro',{}).get('sofr','web search')} — use verified VIX from early_warning signals.
   2Y/10Y Spread={data.get('macro',{}).get('spread_10y2y','web search')} — use verified value.
   Web search: HYG spread, NYSE A/D line direction, earnings revision ratio if available.
   Required signals: VIX, Sector Breadth (X/11 above 50DMA), A/D Line, HYG Spread,
   2Y/10Y Spread, Earnings Revision Ratio.

6. PORTFOLIO ALLOCATION (Section 9)
   Search: "portfolio allocation retirement 5-8 years capital growth preservation {mkt['month_year']}"
   Build allocation for an experienced professional retiring in 5-8 years.
   Profile: capital growth with increasing capital preservation, risk-aware.
   - 5-7 buckets with allocation % and purpose (must sum to 100%)
   - Adjust based on current VIX and macro_indicators in verified data above
   - Include a rebalance_trigger: specific market condition warranting rebalancing

NEVER use web_search to override any verified number (price, beta, VaR, returns).

Return ONLY valid JSON matching this schema. No markdown fences, no prose outside JSON:
{NARRATIVE_SCHEMA}"""