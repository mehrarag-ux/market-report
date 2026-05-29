"""
ONE narrative prompt. The LLM receives REAL numbers and returns ONLY JSON
narrative — it never invents a price. web_search stays on for live news.
"""

import json

NARRATIVE_SCHEMA = """{
  "pulse": "2 sentences summarising the session. Must reference 'Nasdaq 100 (NDX)'.",
  "spotlights": { "<TICKER>": {"rating":"BUY|HOLD|SELL","verdict":"3 sentences: valuation, momentum, key risk","business_risk":"single biggest risk with one number"} },
  "why_paras": ["para: what happened","para: why","para: what it means"],
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
                    "ticker",
                    "name",
                    "price",
                    "day_change",
                    "y1",
                    "hi52",
                    "lo52",
                    "pe",
                    "div",
                    "beta",
                )
            }
            for s in data["spotlights"]
        ],
        "ai_rows": data["ai_rows"],
        "sectors_up": data["winners"],
        "sectors_down": data["losers"],
        "early_warning": data["early_warning"],
        "stw_candidates": data["stw_data"],
    }
    return f"""You are a sell-side analyst writing for a retail investor in Singapore.

{mkt['context']}

These numbers are VERIFIED FACTS from our data layer. Do NOT change any number.
Do NOT invent prices. Reason ONLY over these:

{json.dumps(nums, indent=2, default=str)}

Use web_search ONLY for qualitative news/context (why markets moved, catalysts) —
never to override a number above.

Rules for verdicts (BUY/HOLD/SELL): justify with the actual P/E, price-vs-52W,
1-year momentum and beta shown above. For 'stw' pick exactly 5 from the candidates
with at least one BUY (5-YEAR), one HOLD (1-YEAR), one SELL (EXIT NOW).

Return ONLY valid JSON matching this schema, nothing else (no markdown, no prose):
{NARRATIVE_SCHEMA}"""
