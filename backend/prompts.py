"""
ONE narrative prompt. The LLM receives REAL numbers and returns ONLY JSON
narrative — it never invents a price. web_search stays on for live news
and live analyst price targets.
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
  "opportunity_radar": [{"theme":"name","why":"why NOW + one data point","example":"TICKER"}],
  "portfolio_direction": "1 paragraph: buy / hold / reduce risk, justified by VIX, valuations, macro.",
  "stw": [{"ticker":"X","rating":"BUY|HOLD|SELL","horizon":"5-YEAR|1-YEAR|EXIT NOW","reason":"2 sentences: catalyst + action"}]
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
    return f"""You are a US stock market portfolio manager writing a daily briefing for a retail investor based in Singapore.

{mkt['context']}

These numbers are VERIFIED FACTS from our data layer. Do NOT change any number.
Do NOT invent prices. Reason ONLY over these verified numbers:

{json.dumps(nums, indent=2, default=str)}

Use web_search for exactly two purposes:
1. Qualitative news and catalysts — why markets moved today, what drove individual stocks.
2. For each spotlight ticker, search "[TICKER] analyst price target consensus 2026" to find
   the latest Wall Street consensus price target. Include the source and approximate date
   in the analyst_target field. Note: the 'target' field above is from yfinance and may be
   stale — your web search result takes precedence for analyst_target.

NEVER use web_search to override any verified number above (price, beta, VaR, returns).

Verdict rules (BUY/HOLD/SELL) — must cite actual numbers from the data:
- Reference P/E, price vs 52W high/low, 1-year momentum, beta, AND the analyst consensus target
- Stock trading meaningfully above analyst consensus target → lean SELL or HOLD
- Stock trading meaningfully below analyst consensus target → lean BUY or HOLD
- High beta (>2) warrants explicit risk mention in verdict

For 'stw': pick exactly 5 from stw_candidates. Must include at least:
- 1 × BUY with horizon 5-YEAR
- 1 × HOLD with horizon 1-YEAR
- 1 × SELL with horizon EXIT NOW

Return ONLY valid JSON matching this schema. No markdown fences, no prose outside JSON:
{NARRATIVE_SCHEMA}"""