"""
Daily Market Report — Auto-Emailer + Frontend Updater
Runs via GitHub Actions cron (triggered by cron-job.org at 06:00 SGT Mon-Fri).
Parts: 1=Summary+1B+Spotlights, 2=Commentary+Sectors, 3=3B+Calendar+6B+7
"""

import os, sys, json, re, smtplib, logging, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

BASE_DIR    = os.path.dirname(__file__)
LOG_DIR     = os.path.join(BASE_DIR, "logs")
REPORTS_DIR = os.path.join(BASE_DIR, "..", "frontend", "reports")
os.makedirs(LOG_DIR,     exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "market_report.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
CONFIG = {
    "to_emails": [
        "mehrarag@gmail.com",   
        "pranav2vis@gmail.com",
        "khyatibgupta234@gmail.com",
    ],
    "from_name": "Daily Market Report",

    "watchlist_core": [
        {"symbol": "SPX",  "name": "S&P 500 Index",               "type": "index"},
        {"symbol": "ACWI", "name": "MSCI All Country World Index", "type": "etf"},
        {"symbol": "NDX",  "name": "Nasdaq 100",                  "type": "index"},
        {"symbol": "C",    "name": "Citigroup",                   "type": "stock"},
        {"symbol": "QRVO", "name": "Qorvo",                       "type": "stock"},
    ],

    "watchlist_ai": [
        {"symbol": "NVDA",  "name": "Nvidia",    "type": "stock"},
        {"symbol": "AMD",   "name": "AMD",        "type": "stock"},
        {"symbol": "AVGO",  "name": "Broadcom",   "type": "stock"},
        {"symbol": "GOOGL", "name": "Alphabet",   "type": "stock"},
        {"symbol": "IBM",   "name": "IBM",        "type": "stock"},
        {"symbol": "META",  "name": "Meta",       "type": "stock"},
        {"symbol": "MSFT",  "name": "Microsoft",  "type": "stock"},
        {"symbol": "MU",    "name": "Micron",     "type": "stock"},
        {"symbol": "TSLA",  "name": "Tesla",      "type": "stock"},
        {"symbol": "AAPL",  "name": "Apple",      "type": "stock"},
        {"symbol": "AMZN",  "name": "Amazon",     "type": "stock"},
    ],

    "claude_model": "claude-haiku-4-5-20251001",
    "gemini_model": "gemini-2.0-flash",
    "max_tokens":   8096,
}
# ══════════════════════════════════════════════════════════════════════════════

def is_weekday():   return datetime.datetime.now().weekday() < 5
def today_str():    return datetime.datetime.now().strftime("%A, %B %d, %Y")
def month_year():   return datetime.datetime.now().strftime("%B %Y")
def year_str():     return datetime.datetime.now().strftime("%Y")
def fmt_wl(lst):    return ", ".join(f"{w['symbol']} ({w['name']})" for w in lst)


# ── Prompts ───────────────────────────────────────────────────────────────────

def prompt_part1():
    return f"""You are a financial analyst. Today is {today_str()}. US markets have just closed.

OUTPUT RULES — STRICTLY FOLLOW:
- Output ONLY HTML. Zero plain text outside tags. No "Let me search", no "I found", no thinking.
- Start directly with the banner div below. Nothing before it.
- CRITICAL: Always refer to Nasdaq as "Nasdaq 100 (NDX)" — NEVER "Nasdaq Composite".
- If markets were closed today, note it in an HTML paragraph and use the most recent trading day's data.

Start with exactly this banner:
<div style="background:#0a3d62;color:#fff;padding:16px 20px;border-radius:6px;margin-bottom:24px"><h1 style="margin:0;font-size:20px">Daily Market Report</h1><p style="margin:4px 0 0;font-size:13px;opacity:0.85">{today_str()} — After Market Close | Singapore</p></div>

<h2 style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px">SECTION 1 — Market Summary</h2>

Search for closing prices for S&P 500, Nasdaq 100 (NDX), and Russell 2000 (RUT).
Search separately for each: 1-week %, 1-month % {month_year()}, 1-year %, 52W high/low. Also VIX level and day change.
Table columns EXACTLY: Index | Closing Price | Day Change | 1 Week | 1 Month | 1 Year | 52W High | 52W Low
Green for positive, red for negative.
After table: 2 sentences in a <p> summarising today. MUST reference "Nasdaq 100 (NDX)" not "Nasdaq Composite".

<h2 style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px">SECTION 1B — Early Warning Dashboard</h2>

Using data from your searches above, score each signal GREEN, AMBER, or RED:
1. VIX level: below 20 = GREEN, 20-28 = AMBER, above 28 = RED
2. Market breadth: broad rally (most stocks rising) = GREEN, narrow (only few big names) = AMBER
3. S&P 500 vs trend: normal range = GREEN, more than 10% above recent average = AMBER
4. Consumer confidence trend: stable/rising = GREEN, falling 2+ months = AMBER, sharply falling = RED
5. Bond yield (10Y): below 4.5% = GREEN, 4.5-5% = AMBER, above 5% = RED

HTML table: Signal | Status (use colored badge spans) | What It Means for You
Below table: one line — overall score HEALTHY, CAUTION, or WARNING.
If 3+ signals are AMBER or RED add: <div style="background:#c0392b;color:#fff;padding:8px 12px;border-radius:4px;margin-top:8px;font-weight:bold">⚠ CORRECTION RISK — Consider reducing exposure or adding hedges</div>
Keep entire section under 8 lines.

<h2 style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px">SECTION 2 — Stock Spotlights</h2>

For EACH stock, search for: Closing Price, Day Change, Day Low, Day High, 52-Week High, 52-Week Low, P/E Ratio, Dividend Yield, Analyst Consensus, Price Target, Next Earnings Date, Latest News Headlines (2-3 in a <ul>).
Present as 2-column table (Metric | Value).
CRITICAL: Use the SAME closing price consistently throughout — search once, use that price everywhere.

After the table write:
1. <p><strong>BUY / HOLD / SELL</strong> — 3 sentences on valuation, momentum, key risk.</p>
2. Quantitative Risk box:
<div style="background:#f8f9fa;border-left:4px solid #0a3d62;padding:12px 14px;margin-top:12px;font-size:13px">
<strong>Quantitative Risk Metrics</strong>
<table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:8px">
<tr><th style="background:#0a3d62;color:#fff;padding:6px 8px;text-align:left">Risk Metric</th><th style="background:#0a3d62;color:#fff;padding:6px 8px;text-align:left">Value</th><th style="background:#0a3d62;color:#fff;padding:6px 8px;text-align:left">Plain English Meaning</th></tr>
[Row 1: Beta 1Y vs S&P 500 — search "[TICKER] beta S&P 500". Calculate if needed: stock 52W % / S&P 500 52W %. Example: "Beta 1.42 — For every 10% S&P 500 falls, stock falls ~14.2%"]
[Row 2: Daily VaR 95% — avg daily % move x 1.65. As % and $USD on $10K. Example: "2.8% / $280 per $10K"]
[Row 3: Daily VaR 99% — avg daily % move x 2.33. As % and $USD on $10K. Example: "3.9% / $390 per $10K"]
[Row 4: Key Business Risk — biggest specific risk with one number. Example: "~30% revenue from Apple"]
</table>
</div>

<h3 style="color:#0a3d62">Stock 1: Citigroup (C)</h3>
[search and write table + recommendation + risk box]

<h3 style="color:#0a3d62">Stock 2: Qorvo (QRVO)</h3>
[search and write table + recommendation + risk box]

Use: <table style="width:100%;border-collapse:collapse;font-size:13px;margin:12px 0">
<th style="background:#0a3d62;color:#fff;padding:8px;text-align:left;font-size:11px">
<td style="padding:8px;border-bottom:1px solid #eee;font-size:13px">
Positive: <span style="color:#1a7a3c;font-weight:bold"> Negative: <span style="color:#c0392b;font-weight:bold">"""


def prompt_part2():
    return f"""You are a financial analyst. Today is {today_str()}.

OUTPUT RULES — STRICTLY FOLLOW:
- Output ONLY HTML. Zero plain text outside tags. No "Let me search", no "I found", no thinking.
- Start directly with the first h2 heading. Nothing before it.
- Do NOT generate any watchlist table. Only write Sections 4 and 5.

<h2 style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px">SECTION 4 — Why Markets Moved Today</h2>

Search for main market drivers today. Write 3 <p> paragraphs: what happened, why, what it means for investors.
Name specific stocks, events, Fed news. No jargon without explanation.

<h2 style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px">SECTION 5 — Sector Rotation and Macro</h2>

Top 3 winning sectors with % in a <ul> list. Top 2 losing sectors with % in a <ul> list.
Then 3 macro bullet points in a <ul> — one plain-English sentence each on investor impact.

Use same table/color styles as Part 1."""


def prompt_part3():
    ai = fmt_wl(CONFIG["watchlist_ai"])
    return f"""You are a financial analyst. Today is {today_str()}.

OUTPUT RULES — STRICTLY FOLLOW:
- Output ONLY HTML. Zero plain text outside tags. No reasoning, no "Let me search", no thinking.
- No markdown code fences (no ```html). Pure HTML only.
- Start directly with the first h2 heading. Nothing before it.
- Write sections in EXACTLY this order: AI Watchlist first, then Calendar, then 6B, then 7.

<h2 style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px">AI and Magnificent 7 Watchlist</h2>

Search each ticker individually: {ai}
For each ticker search for: price, day change %, 1-week %, 1-month %, 1-year %, 52W low, 52W high, and Beta vs S&P 500.
To find Beta: search "[TICKER] beta" or "[TICKER] beta vs S&P 500". If not found, calculate: (stock 52W % move) / (S&P 500 52W % move).
CRITICAL: The table MUST have exactly 9 columns in this exact order:
Ticker | Company | Price | Day Change | 1 Week | 1 Month | 1 Year | 52W Low | 52W High | Beta
Do NOT skip the Beta column. If Beta is genuinely unavailable after 2 searches, write "N/A" in that cell.
Green for positive %, red for negative %.

<h2 style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px">SECTION 6 — Earnings and Economic Calendar</h2>

Next 5 earnings (table: Company | Ticker | Date).
Top 3 economic releases this week (table: Event | Date | Why It Matters — one sentence).

<h2 style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px">SECTION 6B — Market Opportunity Radar</h2>

Based on today's data, identify top 3 themes/sectors offering value for medium-term (1-3 year) and long-term (3-5 year) investors.
For each theme: name, why it offers value NOW with one specific data point, one example stock.
Then one paragraph "Portfolio Direction" — good time to buy, hold, or reduce risk, and why.
Base on: VIX level, market valuation, earnings trends, macro data. Keep under 10 lines. Be direct and specific.

<h2 style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px">SECTION 7 — Stocks to Watch</h2>

Pick 5 stocks from Mag7 (AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA) and AI semis (AMD,AVGO,IBM,MU,QRVO,C).
Required: at least 1 BUY (5-year), 1 HOLD (1-year), 1 SELL (exit now).
Use EXACTLY this structure for each entry:
<div class="stw-entry">
<p><strong>TICKER — Full Company Name</strong> | Price: $X.XX | <strong>BUY</strong> | Horizon: 5-YEAR</p>
<p>Rationale: 2 sentences on catalyst and what investor should do.</p>
</div>

End with:
<p style="font-size:11px;color:#888;border-top:1px solid #eee;padding-top:12px;margin-top:32px">Auto-generated by AI for informational purposes only. Not financial advice.</p>

Use same table/color styles as previous parts."""


# ── Post-process ──────────────────────────────────────────────────────────────
REASONING_PREFIXES = (
    "I ", "Let me", "Now ", "Based ", "The ", "Here ", "This ",
    "Note", "Please", "Since", "However", "Given", "According",
    "I'll", "I've", "I'm", "I can", "I need", "I will",
    "US markets", "The market", "The data", "The last",
)

def clean_html(raw: str) -> str:
    # Strip markdown code fences
    raw = re.sub(r'```html?\s*', '', raw, flags=re.I)
    raw = re.sub(r'```\s*', '', raw)
    lines = raw.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue
        if stripped.startswith('<') or stripped.startswith('&'):
            cleaned.append(line)
        elif stripped.endswith('>') or stripped.endswith('/>'):
            cleaned.append(line)
        elif re.match(r"^(" + "|".join(re.escape(p) for p in REASONING_PREFIXES) + ")", stripped):
            log.debug(f"Stripped reasoning: {stripped[:80]}")
        else:
            cleaned.append(line)
    return "\n".join(cleaned)


# ── AI Clients ────────────────────────────────────────────────────────────────
def call_claude(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=CONFIG["claude_model"],
        max_tokens=CONFIG["max_tokens"],
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(b.text for b in resp.content if hasattr(b, "text") and b.text.strip())

def call_gemini(prompt: str) -> str:
    import urllib.request
    key = os.environ["GEMINI_API_KEY"]
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{CONFIG['gemini_model']}:generateContent?key={key}")
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": CONFIG["max_tokens"]},
        "tools": [{"google_search": {}}],
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    parts = data["candidates"][0]["content"]["parts"]
    return "\n".join(p["text"] for p in parts if "text" in p)

def generate_section(label: str, prompt: str) -> str:
    raw = ""
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            log.info(f"{label} — using Claude...")
            raw = call_claude(prompt)
        except Exception as e:
            log.warning(f"Claude failed ({e}) — trying Gemini")
    if not raw and os.getenv("GEMINI_API_KEY"):
        log.info(f"{label} — using Gemini...")
        raw = call_gemini(prompt)
    if not raw:
        raise EnvironmentError("No AI API key found. Set ANTHROPIC_API_KEY or GEMINI_API_KEY.")
    return clean_html(raw)

def generate_report():
    h1 = generate_section("Part 1 (Summary+1B+Spotlights)", prompt_part1())
    log.info(f"Part 1: {len(h1):,} chars")

    h2 = generate_section("Part 2 (Commentary+Sectors)", prompt_part2())
    # Strip Section 3A if AI still generates it despite prompt instructions
    h2 = re.sub(r'<h2[^>]*>.*?(?:3A|Core Watchlist).*?</h2>.*?(?=<h2[^>]*>|$)', '', h2, flags=re.S | re.I)
    log.info(f"Part 2: {len(h2):,} chars")

    h3 = generate_section("Part 3 (AI Watchlist+Calendar+6B+STW)", prompt_part3())
    log.info(f"Part 3: {len(h3):,} chars")
    return h1, h2, h3


# ── Structured JSON extraction ────────────────────────────────────────────────
def strip_tags(html: str) -> str:
    return re.sub(r'<[^>]+>', ' ', html).strip()

def parse_tables(html: str):
    tables = []
    for tbl in re.findall(r'<table[^>]*>(.*?)</table>', html, re.S | re.I):
        rows = []
        for row in re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.S | re.I):
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.S | re.I)
            clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            if any(clean):
                rows.append(clean)
        if rows:
            tables.append(rows)
    return tables

def rows_to_dicts(rows):
    if len(rows) < 2:
        return []
    headers = [h.lower().replace(' ', '_').replace('/', '_').strip() for h in rows[0]]
    result = []
    for row in rows[1:]:
        obj = {headers[i]: (row[i] if i < len(row) else '') for i in range(len(headers))}
        if any(v for v in obj.values()):
            result.append(obj)
    return result

def find_table_by_headers(tables, *keywords):
    for tbl in tables:
        if not tbl:
            continue
        header_str = ' '.join(tbl[0]).lower()
        if all(kw.lower() in header_str for kw in keywords):
            return tbl
    return []

def extract_structured(h1: str, h2: str, h3: str) -> dict:
    tbls1 = parse_tables(h1)
    tbls3 = parse_tables(h3)

    # Market summary
    mkt_tbl = find_table_by_headers(tbls1, 'index', 'closing')
    if not mkt_tbl:
        mkt_tbl = find_table_by_headers(tbls1, 'index', 'change')
    if not mkt_tbl:
        mkt_tbl = next((t for t in tbls1 if t and len(t[0]) >= 6), [])
    mkt_data = rows_to_dicts(mkt_tbl)

    # Pulse sentence
    pulse = ''
    for m in re.finditer(r'<p[^>]*>(.*?)</p>', h1, re.S | re.I):
        txt = strip_tags(m.group(1))
        if len(txt) > 80 and any(w in txt for w in ['S&P', 'Nasdaq', 'market', 'session']):
            pulse = txt
            break

    # Early Warning (1B)
    ew_match = re.search(r'(<h2[^>]*>.*?1B.*?</h2>.*?)(?=<h2[^>]*>.*?(?:SECTION 2|Stock Spotlight)|$)', h1, re.S | re.I)
    early_warning = ew_match.group(1).strip() if ew_match else None

    # Spotlights raw HTML
    spot_html_match = re.search(r'<h2[^>]*>.*?SECTION 2.*?</h2>(.*?)(?=<h2[^>]*>|$)', h1, re.S | re.I)
    spotlights_html = spot_html_match.group(1).strip() if spot_html_match else None

    # Spotlights structured (fallback)
    spot_tables = [t for t in tbls1 if t and len(t[0]) == 2 and len(t) >= 5]
    tickers = ['C', 'QRVO']

    def build_spot(rows, ticker):
        d = {k: '' for k in ['ticker', 'name', 'price', 'day_change', 'day_low', 'day_high',
                              'w52_hi', 'w52_lo', 'pe', 'div', 'analyst', 'target',
                              'earnings', 'news', 'rating', 'verdict']}
        d['ticker'] = ticker
        d['name'] = {'C': 'Citigroup', 'QRVO': 'Qorvo'}.get(ticker, ticker)
        for r in rows:
            if len(r) < 2:
                continue
            k, v = r[0].lower(), r[1]
            if ('clos' in k or k.strip() == 'price') and 'target' not in k: d['price'] = v
            elif 'day change' in k: d['day_change'] = v
            elif 'day low' in k:    d['day_low'] = v
            elif 'day high' in k:   d['day_high'] = v
            elif '52' in k and 'high' in k: d['w52_hi'] = v
            elif '52' in k and 'low' in k:  d['w52_lo'] = v
            elif 'p/e' in k or 'pe ratio' in k: d['pe'] = v
            elif 'div' in k:        d['div'] = v
            elif 'consensus' in k or ('analyst' in k and 'target' not in k): d['analyst'] = v
            elif 'target' in k:     d['target'] = v
            elif 'earn' in k and 'next' in k: d['earnings'] = v
        return d

    spots = []
    h3_sections = re.split(r'<h3[^>]*>', h1, flags=re.I)
    for i, tbl in enumerate(spot_tables[:2]):
        sp = build_spot(tbl, tickers[i] if i < len(tickers) else '')
        if i + 1 < len(h3_sections):
            sec_txt = strip_tags(h3_sections[i + 1])
            m = re.search(r'\b(BUY|HOLD|SELL)\b', sec_txt)
            if m:
                sp['rating'] = m.group(1)
                idx = sec_txt.find(m.group(1))
                sp['verdict'] = sec_txt[max(0, idx - 10): idx + 500].strip()
        spots.append(sp)

    # AI watchlist — find by ticker+company+beta headers
    ai_tbl = find_table_by_headers(tbls3, 'ticker', 'company', 'beta')
    if not ai_tbl:
        ai_tbl = find_table_by_headers(tbls3, 'ticker', 'company')
    if not ai_tbl:
        ai_tbl = find_table_by_headers(tbls3, 'ticker', 'price', 'change')
    if not ai_tbl:
        ai_tbl = next((t for t in sorted(tbls3, key=lambda x: len(x[0]) if x else 0, reverse=True)
                       if t and len(t[0]) >= 5), [])
    ai_rows = rows_to_dicts(ai_tbl)

    # Why moved
    why_match = re.search(r'SECTION 4[^<]*</h2>(.*?)(?=<h2|$)', h2, re.S | re.I)
    why_text  = strip_tags(why_match.group(1)) if why_match else ''
    why_paras = [p.strip() for p in re.split(r'\n{2,}', why_text) if len(p.strip()) > 60][:4]

    # Sectors
    sec5_match = re.search(r'SECTION 5[^<]*</h2>(.*?)(?=<h2|$)', h2, re.S | re.I)
    sec5_text  = re.sub(r'<[^>]+>', '\n', sec5_match.group(1)) if sec5_match else ''
    winners, losers = [], []
    for line in sec5_text.splitlines():
        line = line.strip()
        pm = re.search(r'([+\-]\d+\.?\d*%)', line)
        if not pm or len(line) < 5:
            continue
        name = re.sub(r'[+\-]\d+\.?\d*%.*', '', line).strip(' -•:*')
        if not name:
            continue
        entry = {'name': name, 'pct': pm.group(1)}
        if pm.group(1).startswith('+'):
            winners.append(entry)
        else:
            losers.append(entry)
    macro_lines = [l.strip() for l in sec5_text.splitlines()
                   if len(l.strip()) > 40
                   and not re.search(r'[+\-]\d+\.?\d*%', l)
                   and not re.search(r'^(section|winning|losing|top|worst)', l.strip(), re.I)][:3]

    # Calendar
    earn_tbl = find_table_by_headers(tbls3, 'company', 'ticker')
    if not earn_tbl:
        earn_tbl = find_table_by_headers(tbls3, 'company', 'date')
    econ_tbl = find_table_by_headers(tbls3, 'event', 'date')
    if not econ_tbl:
        econ_tbl = find_table_by_headers(tbls3, 'event', 'matters')

    # Opportunity Radar (6B)
    or_match = re.search(r'(<h2[^>]*>.*?6B.*?</h2>.*?)(?=<h2[^>]*>.*?(?:SECTION 7|Stocks to Watch)|$)', h3, re.S | re.I)
    opportunity_radar = or_match.group(1).strip() if or_match else None

    # Stocks to watch
    stw = []
    for block in re.findall(r'<div[^>]*class=["\']stw-entry["\'][^>]*>(.*?)</div>', h3, re.S | re.I):
        txt = strip_tags(block)
        rm  = re.search(r'\b(BUY|HOLD|SELL)\b', txt)
        tm  = re.search(r'\b([A-Z]{2,5})\b', txt)
        pm  = re.search(r'\$[\d,]+\.?\d*', txt)
        hm  = re.search(r'(5-YEAR|1-YEAR|EXIT NOW)', txt)
        nm  = re.search(r'—\s*(.+?)\s*\|', txt)
        if rm and tm:
            stw.append({
                'ticker':  tm.group(1),
                'name':    nm.group(1).strip() if nm else tm.group(1),
                'rating':  rm.group(1),
                'price':   pm.group(0) if pm else '',
                'horizon': hm.group(1) if hm else (
                    '5-YEAR' if rm.group(1) == 'BUY' else
                    '1-YEAR' if rm.group(1) == 'HOLD' else 'EXIT NOW'),
                'reason':  txt[:500].strip(),
            })
    if not stw:
        sec7_match = re.search(r'SECTION 7[^<]*</h2>(.*?)(?=<p style[^>]*font-size:11px|$)', h3, re.S | re.I)
        if sec7_match:
            for block in re.split(r'\n{2,}', strip_tags(sec7_match.group(1))):
                block = block.strip()
                rm = re.search(r'\b(BUY|HOLD|SELL)\b', block)
                tm = re.search(r'\b([A-Z]{2,5})\b', block)
                pm = re.search(r'\$[\d,]+\.?\d*', block)
                nm = re.search(r'—\s*(.+?)\s*\|', block)
                if rm and tm and len(block) > 40:
                    stw.append({
                        'ticker':  tm.group(1),
                        'name':    nm.group(1).strip() if nm else tm.group(1),
                        'rating':  rm.group(1),
                        'price':   pm.group(0) if pm else '',
                        'horizon': ('5-YEAR' if rm.group(1) == 'BUY' else
                                    '1-YEAR' if rm.group(1) == 'HOLD' else 'EXIT NOW'),
                        'reason':  block[:500],
                    })

    return {
        'date':              datetime.datetime.now().strftime("%Y-%m-%d"),
        'generated':         datetime.datetime.now().isoformat(),
        'mkt_data':          mkt_data,
        'pulse':             pulse,
        'early_warning':     early_warning,
        'spotlights_html':   spotlights_html,
        'spotlights':        spots,
        'ai_rows':           ai_rows,
        'why_paras':         why_paras,
        'winners':           winners[:3],
        'losers':            losers[:2],
        'macro':             macro_lines,
        'earnings':          rows_to_dicts(earn_tbl)[:5],
        'econ':              rows_to_dicts(econ_tbl)[:3],
        'opportunity_radar': opportunity_radar,
        'stw':               stw[:5],
    }


# ── Save ──────────────────────────────────────────────────────────────────────
def save_report(html: str, h1='', h2='', h3=''):
    date_str  = datetime.datetime.now().strftime("%Y-%m-%d")
    html_file = f"report_{date_str}.html"
    html_path = os.path.join(REPORTS_DIR, html_file)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    log.info(f"HTML saved -> {html_path}")

    with open(os.path.join(REPORTS_DIR, "latest.html"), "w", encoding="utf-8") as f:
        f.write(html)

    try:
        data = extract_structured(h1, h2, h3)
        for fname in [f"report_{date_str}.json", "latest.json"]:
            with open(os.path.join(REPORTS_DIR, fname), "w") as f:
                json.dump(data, f, indent=2)
        log.info(f"JSON saved ({len(data['ai_rows'])} AI rows, {len(data['stw'])} STW)")
    except Exception as e:
        log.warning(f"JSON extraction failed: {e}")

    index_path = os.path.join(REPORTS_DIR, "index.json")
    try:
        with open(index_path) as f:
            index = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        index = []
    if not any(r["file"] == html_file for r in index):
        index.insert(0, {"date": date_str, "file": html_file,
                          "generated_at": datetime.datetime.now().isoformat()})
    index = index[:30]
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    log.info(f"index.json updated ({len(index)} reports)")


# ── PDF ───────────────────────────────────────────────────────────────────────
def generate_pdf(html: str, date_str: str):
    try:
        from weasyprint import HTML, CSS
        pdf_path = os.path.join(REPORTS_DIR, f"report_{date_str}.pdf")
        CSS_PAGE  = CSS(string="@page { size: A4 landscape; margin: 1.2cm; }")
        HTML(string=html).write_pdf(pdf_path, stylesheets=[CSS_PAGE])
        log.info(f"PDF saved -> {pdf_path}")
        return pdf_path
    except Exception as e:
        log.warning(f"PDF skipped: {e}")
        return None


# ── Email ─────────────────────────────────────────────────────────────────────
def send_email(html_body: str, pdf_path: str = None):
    smtp_user = os.getenv("GMAIL_ADDRESS")
    smtp_pass = os.getenv("GMAIL_APP_PASSWORD")
    if not smtp_user or not smtp_pass:
        raise EnvironmentError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set.")
    today_label = datetime.datetime.now().strftime("%A, %B %d, %Y")
    recipients  = CONFIG["to_emails"]
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Daily Market Report — {today_label}"
    msg["From"]    = f"{CONFIG['from_name']} <{smtp_user}>"
    msg["To"]      = ", ".join(recipients)
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(f"Daily market report for {today_label}. View in HTML client.", "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)
    if pdf_path:
        try:
            from email.mime.application import MIMEApplication
            with open(pdf_path, "rb") as f:
                att = MIMEApplication(f.read(), _subtype="pdf")
            att.add_header("Content-Disposition", "attachment",
                           filename=f"MarketReport_{datetime.datetime.now().strftime('%Y-%m-%d')}.pdf")
            msg.attach(att)
            log.info("PDF attached to email")
        except Exception as e:
            log.warning(f"PDF attach failed: {e}")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(smtp_user, smtp_pass)
        s.sendmail(smtp_user, recipients, msg.as_string())
    log.info(f"Email sent to: {', '.join(recipients)}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("Daily Market Report — starting")
    if not is_weekday() and "--force" not in sys.argv:
        log.info("Weekend — skipping. Pass --force to override.")
        return
    try:
        h1, h2, h3 = generate_report()
        html = h1 + "\n<br>\n" + h2 + "\n<br>\n" + h3
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        # Reorder: inject 3B after sections 4+5, before calendar
        split_marker = re.search(r'<h2[^>]*>.*?SECTION 6\b.*?</h2>', h3, re.S | re.I)
        if split_marker:
            h3_top  = h3[:split_marker.start()]   # AI watchlist block
            h3_rest = h3[split_marker.start():]   # Section 6, 6B, 7
        else:
            h3_top  = ''
            h3_rest = h3
        html = h1 + "\n<br>\n" + h2 + "\n<br>\n" + h3_top + "\n<br>\n" + h3_rest

        save_report(html, h1, h2, h3)
        pdf_path = generate_pdf(html, date_str)
        send_email(html, pdf_path)
        log.info("Completed successfully ✓")
    except Exception as e:
        log.exception(f"Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()