"""
Daily Market Report — Auto-Emailer + Frontend Updater
Runs via GitHub Actions cron. Writes reports to frontend/reports/ for Vercel.
3-part generation: Part1=Spotlights, Part2=Core watchlist, Part3=AI watchlist+commentary
"""

import os, sys, json, smtplib, logging, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

# ── Directories ────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(__file__)
LOG_DIR     = os.path.join(BASE_DIR, "logs")
REPORTS_DIR = os.path.join(BASE_DIR, "..", "frontend", "reports")
# Resolves to: frontend/reports/ relative to repo root
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

    # Core watchlist — indexes + spotlight stocks
    "watchlist_core": [
        {"symbol": "SPX",  "name": "S&P 500 Index", "type": "index"},
        {"symbol": "NDX",  "name": "Nasdaq 100",    "type": "index"},
        {"symbol": "C",    "name": "Citigroup",     "type": "stock"},
        {"symbol": "QRVO", "name": "Qorvo",         "type": "stock"},
    ],

    # AI / Mag7 watchlist — separate table in the report
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
    ],

    "claude_model": "claude-haiku-4-5-20251001",
    "gemini_model": "gemini-2.0-flash",
    "max_tokens":   8096,
}
# ══════════════════════════════════════════════════════════════════════════════

def is_weekday():  return datetime.datetime.now().weekday() < 5
def today_str():   return datetime.datetime.now().strftime("%A, %B %d, %Y")
def month_year():  return datetime.datetime.now().strftime("%B %Y")
def year():        return datetime.datetime.now().strftime("%Y")

def fmt_watchlist(lst):
    return ", ".join(f"{w['symbol']} ({w['name']})" for w in lst)

HTML_RULES = """
Format output as clean HTML for email.
Outer wrapper: <div style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;padding:20px;color:#1a1a1a;line-height:1.6">
Section headings: <h2 style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px">
Tables: <table style="width:100%;border-collapse:collapse;font-size:13px;margin:12px 0">
Table header cells: <th style="background:#0a3d62;color:#fff;padding:8px;text-align:left;font-size:11px">
Table data cells: <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px">
Positive numbers: <span style="color:#1a7a3c;font-weight:bold">
Negative numbers: <span style="color:#c0392b;font-weight:bold">
"""

SEARCH_RULES = """
Always search for real data — never invent numbers.
If a % change is not directly available, find prices from two dates and calculate it.
Only write "Unavailable" after searching at least 3 times with different queries.
Always refer to the Nasdaq index as "Nasdaq 100" (ticker: NDX). Never "Nasdaq Composite".
Write everything in plain English — no jargon without a brief explanation.
CRITICAL: Your response must contain ONLY valid HTML. Do NOT include any reasoning, commentary,
thinking steps, or plain text outside of HTML tags. Every word of your output must be inside
an HTML tag. No markdown. No "Let me search..." or "I found..." text. Pure HTML only.
"""

# ── PART 1: Market Summary + Stock Spotlights ─────────────────────────────────
def prompt_part1():
    return f"""You are a professional financial analyst writing a daily after-market-close report for a retail investor in Singapore.
Today is {today_str()}. The US stock market has just closed.

{SEARCH_RULES}

Write ONLY these two sections:

SECTION 1 — Market Summary
Search for today's closing prices for S&P 500 and Nasdaq 100 (ticker NDX).
Search separately for:
  - S&P 500: 1-week %, 1-month % ({month_year()}), 1-year %, 52W high/low
  - Nasdaq 100: 1-week %, 1-month % ({month_year()}), 1-year %, 52W high/low
  - VIX: current level, day change, one-sentence plain-English explanation
HTML table: Index | Closing Price | Day Change | 1 Week | 1 Month | 1 Year | 52W High | 52W Low
Below the table: 2 sentences summarising today's session and why.

SECTION 2 — Stock Spotlights
For each stock: closing price, day change, today's day low, today's day high,
52W high, 52W low, P/E ratio, dividend yield, analyst consensus, price target,
next earnings date, latest 2–3 news headlines.
Present each as an HTML table (Metric | Value), then:
  - Clear BUY / HOLD / SELL recommendation
  - 3-sentence plain-English explanation covering valuation, momentum, and key risk

Stock 1: Citigroup (C)
Stock 2: Qorvo (QRVO)

Start with this exact banner:
<div style="background:#0a3d62;color:#ffffff;padding:16px 20px;border-radius:6px;margin-bottom:24px">
<h1 style="margin:0;font-size:20px">Daily Market Report</h1>
<p style="margin:4px 0 0;font-size:13px;opacity:0.85">{today_str()} — After Market Close | Singapore</p>
</div>

{HTML_RULES}"""

# ── PART 2: Core Watchlist + Market Commentary + Sectors + Calendar ───────────
def prompt_part2():
    core = fmt_watchlist(CONFIG["watchlist_core"])
    return f"""You are a professional financial analyst writing part 2 of a daily after-market-close report for a retail investor in Singapore.
Today is {today_str()}.

{SEARCH_RULES}

Write ONLY these sections in order:

SECTION 3A — Core Watchlist Performance
Search each ticker one at a time: {core}
For each: closing price, day change %, 1-week %, 1-month %, 1-year %, 52W low, 52W high.
If % not directly available, find historical prices and calculate.
Label this table: "Core Watchlist"
HTML table: Name | Price | Day Change | 1 Week | 1 Month | 1 Year | 52W Low | 52W High
Green for positive, red for negative.

SECTION 4 — Why Markets Moved Today
Search for the main drivers of today's session.
3 plain-English paragraphs: what happened, why it happened, what it means for retail investors.
Name specific stocks, events, Fed news, economic data. No jargon without explanation.

SECTION 5 — Sector Rotation & Macro Highlights
Top 3 winning sectors and top 2 losing sectors with % moves.
3 bullet points on key macro data released today (Fed, CPI, jobs, oil, yields).
One plain-English sentence per bullet on investor impact.

SECTION 6 — Earnings & Economic Calendar (keep concise)
Next 5 days: top 5 earnings — company, ticker, date.
This week: top 3 economic releases — name, date, one-sentence importance.

{HTML_RULES}"""

# ── PART 3: AI/Mag7 Watchlist + Stocks to Watch ──────────────────────────────
def prompt_part3():
    ai = fmt_watchlist(CONFIG["watchlist_ai"])
    return f"""You are a professional financial analyst writing part 3 of a daily after-market-close report for a retail investor in Singapore.
Today is {today_str()}.

{SEARCH_RULES}

Write ONLY these sections in order:

SECTION 3B — AI & Magnificent 7 Watchlist Performance
Search each ticker one at a time: {ai}
For each: closing price, day change %, 1-week %, 1-month %, 1-year %, 52W low, 52W high.
If % not directly available, find historical prices and calculate.
Label this table: "AI & Mag 7 Watchlist"
HTML table: Name | Price | Day Change | 1 Week | 1 Month | 1 Year | 52W Low | 52W High
Green for positive, red for negative.

SECTION 7 — Stocks to Watch
Pick exactly 5 stocks based on today's market activity and news.
Draw candidates PRIMARILY from the Magnificent 7 (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA)
and the AI/semiconductor universe (AMD, AVGO, IBM, MU, QRVO, C).
You may include 1 wildcard outside this list only if today's news strongly justifies it.
Required mix: at least 1 BUY (5-year long-term), at least 1 HOLD (1-year horizon), at least 1 SELL (exit immediately).
For each: name, ticker, current price, rating + horizon label, and 2-sentence plain-English rationale
covering the specific catalyst today and what an investor should do next.

End the entire report with:
<p style="font-size:11px;color:#888;border-top:1px solid #eee;padding-top:12px;margin-top:32px">
Auto-generated by AI for informational purposes only. Not financial advice.
</p>

{HTML_RULES}"""

# ── AI Clients ────────────────────────────────────────────────────────────────
def call_claude(prompt):
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=CONFIG["claude_model"],
        max_tokens=CONFIG["max_tokens"],
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(b.text for b in resp.content if hasattr(b, "text") and b.text.strip())

def call_gemini(prompt):
    import urllib.request
    key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{CONFIG['gemini_model']}:generateContent?key={key}"
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

def generate_section(label, prompt):
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            log.info(f"{label} — using Claude...")
            return call_claude(prompt)
        except Exception as e:
            log.warning(f"Claude failed ({e}) — falling back to Gemini")
    if os.getenv("GEMINI_API_KEY"):
        log.info(f"{label} — using Gemini...")
        return call_gemini(prompt)
    raise EnvironmentError("No AI API key found. Set ANTHROPIC_API_KEY or GEMINI_API_KEY.")

def generate_report():
    h1 = generate_section("Part 1 (Summary + Spotlights)", prompt_part1())
    log.info(f"Part 1: {len(h1):,} chars")
    h2 = generate_section("Part 2 (Core watchlist + Commentary)", prompt_part2())
    log.info(f"Part 2: {len(h2):,} chars")
    h3 = generate_section("Part 3 (AI watchlist + Stocks to Watch)", prompt_part3())
    log.info(f"Part 3: {len(h3):,} chars")
    return h1 + "\n<br>\n" + h2 + "\n<br>\n" + h3

# ── Save ──────────────────────────────────────────────────────────────────────
def save_report(html):
    date_str  = datetime.datetime.now().strftime("%Y-%m-%d")
    html_file = f"report_{date_str}.html"
    html_path = os.path.join(REPORTS_DIR, html_file)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    log.info(f"HTML saved → {html_path}")

    with open(os.path.join(REPORTS_DIR, "latest.html"), "w", encoding="utf-8") as f:
        f.write(html)
    log.info("latest.html updated")

    index_path = os.path.join(REPORTS_DIR, "index.json")
    try:
        with open(index_path) as f:
            index = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        index = []

    if not any(r["file"] == html_file for r in index):
        index.insert(0, {
            "date": date_str,
            "file": html_file,
            "generated_at": datetime.datetime.now().isoformat(),
        })
    index = index[:30]

    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    log.info(f"index.json updated ({len(index)} reports)")

# ── Email ─────────────────────────────────────────────────────────────────────
def send_email(html_body):
    smtp_user = os.getenv("GMAIL_ADDRESS")
    smtp_pass = os.getenv("GMAIL_APP_PASSWORD")
    if not smtp_user or not smtp_pass:
        raise EnvironmentError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set.")

    today_label = datetime.datetime.now().strftime("%A, %B %d, %Y")
    recipients  = CONFIG["to_emails"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Market Report — {today_label}"
    msg["From"]    = f"{CONFIG['from_name']} <{smtp_user}>"
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(f"Daily market report for {today_label}. View in HTML client.", "plain"))
    msg.attach(MIMEText(html_body, "html"))

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
        html = generate_report()
        save_report(html)
        send_email(html)
        log.info("Completed successfully ✓")
    except Exception as e:
        log.exception(f"Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()