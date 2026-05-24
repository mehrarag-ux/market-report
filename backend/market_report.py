"""
Daily Market Report — Auto-Emailer
Supports Anthropic (Claude) with Gemini fallback.
"""

import os
import sys
import json
import smtplib
import logging
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

load_dotenv()

# ── Directories ────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(__file__)
LOG_DIR     = os.path.join(BASE_DIR, "logs")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
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
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
CONFIG = {
    "to_email":  "mehrarag@gmail.com",
    "from_name": "Daily Market Report",

    # Watchlist — add/remove as needed
    "watchlist": [
        {"symbol": "SPX",  "name": "S&P 500 Index", "type": "index"},
        {"symbol": "NDX",  "name": "Nasdaq 100",    "type": "index"},
        {"symbol": "C",    "name": "Citigroup",     "type": "stock"},
        {"symbol": "QRVO", "name": "Qorvo",         "type": "stock"},
        # {"symbol": "NVDA", "name": "Nvidia",       "type": "stock"},
        # {"symbol": "QQQ",  "name": "Invesco QQQ",  "type": "etf"},
    ],

    # AI models
    "claude_model": "claude-haiku-4-5-20251001",
    "gemini_model": "gemini-2.0-flash",
    "max_tokens":   4096,
}
# ══════════════════════════════════════════════════════════════════════════════


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_weekday() -> bool:
    return datetime.datetime.now().weekday() < 5


def today_str() -> str:
    return datetime.datetime.now().strftime("%A, %B %d, %Y")


def month_year() -> str:
    return datetime.datetime.now().strftime("%B %Y")


def year() -> str:
    return datetime.datetime.now().strftime("%Y")


def watchlist_str() -> str:
    return ", ".join(f"{w['symbol']} ({w['name']})" for w in CONFIG["watchlist"])


# ── Prompts ───────────────────────────────────────────────────────────────────

HTML_RULES = """
Format the output as clean HTML for email.
Outer wrapper: <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;padding:20px;color:#1a1a1a;line-height:1.6">
Section headings: <h2 style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px">
Tables: <table style="width:100%;border-collapse:collapse;font-size:13px;margin:12px 0">
Positive numbers: <span style="color:#1a7a3c;font-weight:bold">
Negative numbers: <span style="color:#c0392b;font-weight:bold">
"""

SEARCH_RULES = """
Always search for real data — never invent numbers.
If a % change is not directly available, find prices from two dates and calculate it yourself.
Only write "Unavailable" after searching at least 3 times with different queries.
Always refer to the Nasdaq index as "Nasdaq 100" (never "Nasdaq Composite").
Write everything in plain English — no jargon without explanation.
"""


def prompt_part1() -> str:
    return f"""You are a professional financial analyst writing a daily after-market-close report for a retail investor in Singapore.
Today is {today_str()}. The US stock market has just closed.

{SEARCH_RULES}

Write ONLY these two sections:

SECTION 1 — Market Summary
Search for today's closing prices and performance for S&P 500 and Nasdaq 100 (ticker NDX).
Search separately for:
  - S&P 500: 1-week %, 1-month % ({month_year()}), 1-year % ({year()}), 52W high/low
  - Nasdaq 100: 1-week %, 1-month % ({month_year()}), 1-year % ({year()}), 52W high/low
  - VIX: current level, day change, and a one-sentence plain-English explanation
Present as an HTML table: Index | Closing Price | Day Change | 1 Week | 1 Month | 1 Year | 52W High | 52W Low
Below the table write 2 sentences summarising how the market performed today and why.

SECTION 2 — Stock Spotlights
For each stock below, search for: closing price, day change, today's day low, today's day high,
52W high, 52W low, P/E ratio, dividend yield, analyst consensus (Buy/Hold/Sell), price target,
next earnings date, and the latest 2–3 news headlines.
Present each stock as an HTML table (Metric | Value), then:
  - Give a clear BUY / HOLD / SELL recommendation
  - Write a 3-sentence plain-English explanation of WHY — covering valuation, momentum, and key risk

Stock 1: Citigroup (C)
Stock 2: Qorvo (QRVO)

Start the response with this banner (no changes):
<div style="background:#0a3d62;color:#ffffff;padding:16px 20px;border-radius:6px;margin-bottom:24px">
<h1 style="margin:0;font-size:20px">Daily Market Report</h1>
<p style="margin:4px 0 0;font-size:13px;opacity:0.85">{today_str()} — After Market Close</p>
</div>

{HTML_RULES}"""


def prompt_part2() -> str:
    return f"""You are a professional financial analyst writing part 2 of a daily after-market-close report for a retail investor in Singapore.
Today is {today_str()}.

{SEARCH_RULES}

Write ONLY these sections (in order):

SECTION 3 — Watchlist Performance Table
Search for each ticker one at a time: {watchlist_str()}
For each: closing price, day change %, 1-week %, 1-month %, 1-year %, 52W low, 52W high.
If a % is not directly available, find historical prices and calculate it.
HTML table: Name | Price | Day Change | 1 Week | 1 Month | 1 Year | 52W Low | 52W High
Green for positive, red for negative.

SECTION 4 — Why Markets Moved Today
Search for the main drivers of today's market session.
Write 3 plain-English paragraphs: what happened, why it happened, what it means for retail investors.
Name specific stocks, events, Fed news, or economic data. No jargon without explanation.

SECTION 5 — Sector Rotation & Macro Highlights
Top 3 winning sectors and top 2 losing sectors with % moves.
3 bullet points on key macro data released today (Fed, CPI, jobs, oil, yields).
One plain-English sentence explaining what each means for investors.

SECTION 6 — Earnings & Economic Calendar (keep concise)
Next 5 days: top 5 earnings reports — company, ticker, date.
This week: top 3 economic data releases — name, date, one-sentence importance.

SECTION 7 — Stocks to Watch
List exactly 3 stocks based on today's market activity.
You MUST include: 1 BUY (5-year long-term horizon), 1 HOLD (1-year horizon), 1 SELL (exit immediately).
For each: name, ticker, price, rating + horizon, and 2 sentences explaining the call in plain English.

End with:
<p style="font-size:11px;color:#888;border-top:1px solid #eee;padding-top:12px;margin-top:32px">
This report is auto-generated by AI for informational purposes only. Not financial advice.
</p>

{HTML_RULES}"""


# ── AI Clients ────────────────────────────────────────────────────────────────

def call_claude(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=CONFIG["claude_model"],
        max_tokens=CONFIG["max_tokens"],
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(b.text for b in response.content if hasattr(b, "text") and b.text.strip())


def call_gemini(prompt: str) -> str:
    import urllib.request
    api_key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{CONFIG['gemini_model']}:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": CONFIG["max_tokens"]},
        "tools": [{"google_search": {}}],
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    parts = data["candidates"][0]["content"]["parts"]
    return "\n".join(p["text"] for p in parts if "text" in p)


def generate_section(prompt: str) -> str:
    """Try Claude first, fall back to Gemini if Claude key missing or fails."""
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            log.info("Using Claude (Anthropic)...")
            return call_claude(prompt)
        except Exception as e:
            log.warning(f"Claude failed: {e} — trying Gemini fallback...")

    if os.getenv("GEMINI_API_KEY"):
        log.info("Using Gemini (Google)...")
        return call_gemini(prompt)

    raise EnvironmentError("No AI API key found. Set ANTHROPIC_API_KEY or GEMINI_API_KEY in .env")


def generate_report() -> str:
    log.info("Generating Part 1 — Market Summary & Spotlights...")
    html1 = generate_section(prompt_part1())
    log.info(f"Part 1 done — {len(html1):,} chars")

    log.info("Generating Part 2 — Watchlist & Commentary...")
    html2 = generate_section(prompt_part2())
    log.info(f"Part 2 done — {len(html2):,} chars")

    return html1 + "\n<br>\n" + html2


# ── Save ──────────────────────────────────────────────────────────────────────

def save_report(html: str):
    date_str  = datetime.datetime.now().strftime("%Y-%m-%d")
    html_path = os.path.join(REPORTS_DIR, f"report_{date_str}.html")
    json_path = os.path.join(REPORTS_DIR, f"report_{date_str}.json")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    log.info(f"HTML saved → {html_path}")

    meta = {"date": date_str, "generated_at": datetime.datetime.now().isoformat(), "file": f"report_{date_str}.html"}
    with open(json_path, "w") as f:
        json.dump(meta, f)

    # PDF
    pdf_path = html_path.replace(".html", ".pdf")
    try:
        from weasyprint import HTML, CSS
        CSS_LANDSCAPE = CSS(string="@page { size: A4 landscape; margin: 1.5cm; }")
        HTML(string=html).write_pdf(pdf_path, stylesheets=[CSS_LANDSCAPE])
        log.info(f"PDF saved → {pdf_path}")
    except Exception as e:
        log.warning(f"PDF skipped: {e}")
        pdf_path = None

    return html_path, pdf_path


# ── Email ─────────────────────────────────────────────────────────────────────

def send_email(html_body: str, pdf_path: str | None = None):
    smtp_user = os.getenv("GMAIL_ADDRESS")
    smtp_pass = os.getenv("GMAIL_APP_PASSWORD")
    if not smtp_user or not smtp_pass:
        raise EnvironmentError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in .env")

    today_label = datetime.datetime.now().strftime("%A, %B %d, %Y")
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Daily Market Report — {today_label}"
    msg["From"]    = f"{CONFIG['from_name']} <{smtp_user}>"
    msg["To"]      = CONFIG["to_email"]

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(f"Daily market report for {today_label}. View in HTML client.", "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    if pdf_path:
        try:
            with open(pdf_path, "rb") as f:
                att = MIMEApplication(f.read(), _subtype="pdf")
            att.add_header("Content-Disposition", "attachment",
                           filename=f"Market_Report_{datetime.datetime.now().strftime('%Y-%m-%d')}.pdf")
            msg.attach(att)
            log.info("PDF attached to email")
        except Exception as e:
            log.warning(f"PDF attach failed: {e}")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, CONFIG["to_email"], msg.as_string())
    log.info(f"Email sent to {CONFIG['to_email']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("Daily Market Report — starting")

    if not is_weekday() and "--force" not in sys.argv:
        log.info("Weekend — skipping. Pass --force to override.")
        return

    try:
        html = generate_report()
        html_path, pdf_path = save_report(html)
        send_email(html, pdf_path)
        log.info("Completed successfully ✓")
    except Exception as e:
        log.exception(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()