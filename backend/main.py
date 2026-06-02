"""
Orchestrator: data → one LLM narrative call → render HTML + JSON → save/email.
Numbers come entirely from data.py (Twelve Data + FRED). LLM writes narrative only.
"""

import os, sys, json, re, smtplib, logging, datetime, time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

from config import CONFIG, REPORTS_DIR, LOG_DIR, SPOTLIGHTS
from data import get_market_context, build_report_data, fundamentals_for
from prompts import narrative_prompt

load_dotenv()
os.makedirs(LOG_DIR, exist_ok=True)
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

C    = lambda v: "#1a7a3c" if (isinstance(v, (int, float)) and v >= 0) else "#c0392b"
TH   = 'style="background:#0a3d62;color:#fff;padding:8px;text-align:left;font-size:11px"'
TD   = 'style="padding:8px;border-bottom:1px solid #eee;font-size:13px"'
TBL  = 'style="width:100%;border-collapse:collapse;font-size:13px;margin:12px 0"'
H2   = 'style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px"'


def span(v, suffix="%"):
    if v is None:
        return '<span style="color:#888">N/A</span>'
    return f'<span style="color:{C(v)};font-weight:bold">{v:+.2f}{suffix}</span>'


def span_str(pct_str):
    try:
        v = float(pct_str.replace("%", ""))
        return f'<span style="color:{C(v)};font-weight:bold">{pct_str}</span>'
    except Exception:
        return pct_str


# ── LLM narrative (single call) ────────────────────────────────────────────────
def get_narrative(mkt, data) -> dict:
    import anthropic
    prompt = narrative_prompt(mkt, data)
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp   = client.messages.create(
        model=CONFIG["claude_model"],
        max_tokens=CONFIG["max_tokens"],
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in resp.content if hasattr(b, "text") and b.text)
    raw = re.sub(r"```json\s*|```\s*", "", raw).strip()
    m   = re.search(r"\{.*\}", raw, re.S)
    try:
        return json.loads(m.group(0) if m else raw)
    except Exception as e:
        log.error(f"narrative JSON parse failed: {e}")
        return {}


# ── HTML renderers ─────────────────────────────────────────────────────────────
def render_indices(rows):
    head = "".join(
        f"<th {TH}>{h}</th>"
        for h in ["Index","Closing Price","Day","1 Week","1 Month","1 Year","52W High","52W Low"]
    )
    body = "".join(
        f"<tr><td {TD}>{r['index']}</td><td {TD}>{r['closing_price']}</td>"
        f"<td {TD}>{span(r['day_change'])}</td><td {TD}>{span(r['1_week'])}</td>"
        f"<td {TD}>{span(r['1_month'])}</td><td {TD}>{span(r['1_year'])}</td>"
        f"<td {TD}>{r['52w_high']}</td><td {TD}>{r['52w_low']}</td></tr>"
        for r in rows
    )
    return f"<table {TBL}><tr>{head}</tr>{body}</table>"


def render_early_warning(ew):
    badge = {"GREEN": "#1a7a3c", "AMBER": "#f59e0b", "RED": "#c0392b", "GREY": "#888"}
    rows  = "".join(
        f"<tr><td {TD}>{s['name']}</td>"
        f"<td {TD}><span style='background:{badge[s['status']]};color:#fff;"
        f"padding:2px 8px;border-radius:3px;font-size:11px'>{s['status']}</span></td>"
        f"<td {TD}>{s['meaning']}</td></tr>"
        for s in ew["signals"]
    )
    head = "".join(f"<th {TH}>{h}</th>" for h in ["Signal","Status","What It Means"])
    warn = (
        '<div style="background:#c0392b;color:#fff;padding:8px 12px;border-radius:4px;'
        'margin-top:8px;font-weight:bold">⚠ CORRECTION RISK — Consider reducing exposure or adding hedges</div>'
        if ew["correction_risk"] else ""
    )
    return (
        f"<table {TBL}><tr>{head}</tr>{rows}</table>"
        f"<p><strong>Overall: {ew['overall']}</strong></p>{warn}"
    )


def render_spotlight(s, narr, fund):
    """fund = pre-fetched fundamentals dict for this ticker."""
    n        = narr.get("spotlights", {}).get(s["ticker"], {})
    dc       = s.get("day_change")
    # day_change is a float % — format it properly with colour
    dc_html  = span(dc) if dc is not None else '<span style="color:#888">N/A</span>'
    # analyst_target comes from LLM web search (fresh); fallback to yfinance value
    at       = n.get("analyst_target") or fund.get("target", "N/A")
    metrics  = [
        ("Closing Price",   s.get("price")),
        ("Day Change",      dc_html),          # ← formatted % with colour
        ("52W High",        s.get("hi52")),
        ("52W Low",         s.get("lo52")),
        ("P/E Ratio",       fund.get("pe",       "N/A")),
        ("Dividend Yield",  fund.get("div",       "N/A")),
        ("Analyst View",    fund.get("analyst",   "N/A")),
        ("Analyst Target",  at),               # ← uses LLM-searched target
        ("Next Earnings",   fund.get("earnings",  "N/A")),
        ("Beta (1Y)",       s.get("beta")),
    ]
    body = "".join(
        f"<tr><td {TD}><strong>{k}</strong></td><td {TD}>{v}</td></tr>"
        for k, v in metrics
    )
    rating   = n.get("rating", "HOLD")
    verdict  = n.get("verdict", "")
    beta_val = s.get("beta") or 1
    risk_rows = (
        f"<tr><td {TD}>Beta 1Y</td><td {TD}>{s.get('beta')}</td>"
        f"<td {TD}>For every 10% the S&P moves, ~{abs(beta_val)*10:.1f}% expected move</td></tr>"
        f"<tr><td {TD}>Daily VaR 95%</td>"
        f"<td {TD}>{s.get('var95_pct')}% / ${s.get('var95_usd'):,.0f} per $10K</td>"
        f"<td {TD}>Typical bad-day loss</td></tr>"
        f"<tr><td {TD}>Daily VaR 99%</td>"
        f"<td {TD}>{s.get('var99_pct')}% / ${s.get('var99_usd'):,.0f} per $10K</td>"
        f"<td {TD}>Extreme-day loss</td></tr>"
        f"<tr><td {TD}>Key Business Risk</td>"
        f"<td {TD} colspan='2'>{n.get('business_risk','')}</td></tr>"
    )
    return (
        f"<h3 style='color:#0a3d62'>{s['name']} ({s['ticker']})</h3>"
        f"<table {TBL}><tr><th {TH}>Metric</th><th {TH}>Value</th></tr>{body}</table>"
        f"<p><strong>{rating}</strong> — {verdict}</p>"
        f"<div style='background:#f8f9fa;border-left:4px solid #0a3d62;padding:12px'>"
        f"<strong>Quantitative Risk Metrics</strong>"
        f"<table {TBL}><tr><th {TH}>Metric</th><th {TH}>Value</th><th {TH}>Plain English</th></tr>"
        f"{risk_rows}</table></div>"
    )


def render_ai_table(rows):
    head = "".join(
        f"<th {TH}>{h}</th>"
        for h in ["Ticker","Company","Price","Day","1 Week","1 Month","1 Year","52W Low","52W High","Beta"]
    )
    body = "".join(
        f"<tr><td {TD}>{r['ticker']}</td><td {TD}>{r['company']}</td><td {TD}>{r['price']}</td>"
        f"<td {TD}>{span(r['day_change'])}</td><td {TD}>{span(r['1_week'])}</td>"
        f"<td {TD}>{span(r['1_month'])}</td><td {TD}>{span(r['1_year'])}</td>"
        f"<td {TD}>{r['52w_low']}</td><td {TD}>{r['52w_high']}</td>"
        f"<td {TD}>{r['beta'] if r['beta'] is not None else 'N/A'}</td></tr>"
        for r in rows
    )
    return f"<table {TBL}><tr>{head}</tr>{body}</table>"


def render_earnings(narr_earnings, fund_cache):
    """
    Renders the earnings table.
    narr_earnings = LLM-sourced list of {company, ticker, date} for broader NDX stocks.
    fund_cache    = yfinance earnings for the 3 spotlights (guaranteed accurate).
    Spotlights are always shown first, then LLM-sourced NDX entries.
    """
    rows = ""
    # Spotlight earnings first — from verified yfinance data
    for s in SPOTLIGHTS:
        date = fund_cache.get(s["symbol"], {}).get("earnings", "N/A")
        rows += (
            f"<tr><td {TD}>{s['name']}</td><td {TD}>{s['symbol']}</td>"
            f"<td {TD}>{date}</td>"
            f"<td {TD}><span style='background:#0a3d62;color:#fff;padding:1px 6px;"
            f"border-radius:3px;font-size:10px'>WATCHLIST</span></td></tr>"
        )
    # Broader NDX earnings from LLM web search
    for e in (narr_earnings or []):
        ticker = e.get("ticker", "")
        # Skip if already shown as spotlight
        if ticker in [s["symbol"] for s in SPOTLIGHTS]:
            continue
        rows += (
            f"<tr><td {TD}>{e.get('company','')}</td><td {TD}>{ticker}</td>"
            f"<td {TD}>{e.get('date','N/A')}</td>"
            f"<td {TD}></td></tr>"
        )
    head = "".join(
        f"<th {TH}>{h}</th>"
        for h in ["Company", "Ticker", "Next Earnings", ""]
    )
    return f"<table {TBL}><tr>{head}</tr>{rows}</table>"


def render_email(mkt, data, narr, fund_cache):
    note = (
        "" if mkt["market_open"]
        else f'<p style="font-size:12px;color:#888">Markets closed today — showing {mkt["last_trading_day"]} close.</p>'
    )
    h  = (
        f'<div style="background:#0a3d62;color:#fff;padding:16px 20px;border-radius:6px;margin-bottom:24px">'
        f'<h1 style="margin:0;font-size:20px">Daily Market Report</h1>'
        f'<p style="margin:4px 0 0;font-size:13px;opacity:.85">'
        f'{mkt["today"]} — After Market Close | Singapore</p></div>{note}'
    )
    h += f'<h2 {H2}>SECTION 1 — Market Summary</h2>{render_indices(data["indices"])}'
    h += f'<p>{narr.get("pulse","")}</p>'
    h += f'<h2 {H2}>SECTION 1B — Early Warning</h2>{render_early_warning(data["early_warning"])}'
    h += f'<h2 {H2}>SECTION 2 — Stock Spotlights</h2>'
    h += "".join(
        render_spotlight(s, narr, fund_cache.get(s["ticker"], {}))
        for s in data["spotlights"]
    )
    h += f'<h2 {H2}>SECTION 3 — AI & Mag 7 Watchlist</h2>{render_ai_table(data["ai_rows"])}'
    h += f'<h2 {H2}>SECTION 4 — Why Markets Moved</h2>'
    h += "".join(f"<p>{p}</p>" for p in narr.get("why_paras", []))
    win = "".join(f"<li>{w['name']}: {span_str(w['pct'])}</li>" for w in data["winners"])
    los = "".join(f"<li>{l['name']}: {span_str(l['pct'])}</li>" for l in data["losers"])
    mac = "".join(f"<li>{m}</li>" for m in narr.get("macro", []))
    h += (
        f'<h2 {H2}>SECTION 5 — Sector Rotation & Macro</h2>'
        f'<strong>Winners</strong><ul>{win}</ul>'
        f'<strong>Losers</strong><ul>{los}</ul>'
        f'<strong>Macro</strong><ul>{mac}</ul>'
    )
    # Earnings — spotlights (yfinance) + broader NDX (LLM web search)
    h += (
        f'<h2 {H2}>SECTION 6 — Earnings Calendar</h2>'
        f'<p style="font-size:11px;color:#888;margin-bottom:8px">'
        f'Watchlist stocks verified. Broader NDX dates sourced via web search — confirm before trading.</p>'
        + render_earnings(narr.get("earnings_calendar", []), fund_cache)
    )
    radar = "".join(
        f"<li><strong>{r.get('theme')}</strong> — {r.get('why')} (e.g. {r.get('example')})</li>"
        for r in narr.get("opportunity_radar", [])
    )
    h += (
        f'<h2 {H2}>SECTION 6B — Opportunity Radar</h2>'
        f'<ul>{radar}</ul><p>{narr.get("portfolio_direction","")}</p>'
    )
    stw = "".join(
        f'<div class="stw-entry"><p><strong>{s.get("ticker")}</strong> | '
        f'Price: ${data["stw_data"].get(s.get("ticker"), {}).get("price", s.get("price_note", ""))} | '
        f'<strong>{s.get("rating")}</strong> | Horizon: {s.get("horizon")}</p>'
        f'<p>{s.get("reason")}</p></div>'
        for s in narr.get("stw", [])
    )
    h += f'<h2 {H2}>SECTION 7 — Stocks to Watch</h2>{stw}'
    h += (
        '<p style="font-size:11px;color:#888;border-top:1px solid #eee;'
        'padding-top:12px;margin-top:32px">Auto-generated. Prices from public market data; '
        'commentary AI-generated. Not financial advice.</p>'
    )
    return h


# ── Frontend JSON ──────────────────────────────────────────────────────────────
def build_frontend_json(mkt, data, narr, fund_cache):
    sp = [
        {
            "ticker":     s["ticker"],
            "name":       s["name"],
            "price":      s.get("price"),
            "day_change": s.get("day_change"),
            "rating":     narr.get("spotlights", {}).get(s["ticker"], {}).get("rating"),
            "verdict":    narr.get("spotlights", {}).get(s["ticker"], {}).get("verdict"),
        }
        for s in data["spotlights"]
    ]
    spot_html = "".join(
        render_spotlight(s, narr, fund_cache.get(s["ticker"], {}))
        for s in data["spotlights"]
    )
    stw = [
        {
            **s,
            "price": f"${data['stw_data'].get(s.get('ticker'), {}).get('price', s.get('price_note', ''))}",
            "name":  s.get("ticker"),
        }
        for s in narr.get("stw", [])
    ]
    fmt_pct = lambda v: f"{v:+.2f}%" if v is not None else "—"

    # Earnings: spotlight verified + LLM-sourced NDX
    earnings_out = [
        {
            "company": s["name"],
            "ticker":  s["symbol"],
            "date":    fund_cache.get(s["symbol"], {}).get("earnings", "N/A"),
        }
        for s in SPOTLIGHTS
    ]
    spotlight_tickers = {s["symbol"] for s in SPOTLIGHTS}
    for e in (narr.get("earnings_calendar") or []):
        if e.get("ticker") not in spotlight_tickers:
            earnings_out.append(e)

    return {
        "date":           datetime.date.today().isoformat(),
        "generated":      datetime.datetime.now().isoformat(),
        "mkt_data": [
            {
                "index":         r["index"],
                "closing_price": r["closing_price"],
                "day_change":    fmt_pct(r["day_change"]),
                "1_week":        fmt_pct(r["1_week"]),
                "1_month":       fmt_pct(r["1_month"]),
                "1_year":        fmt_pct(r["1_year"]),
                "52w_high":      r["52w_high"],
                "52w_low":       r["52w_low"],
            }
            for r in data["indices"]
        ],
        "pulse":           narr.get("pulse", ""),
        "early_warning":   render_early_warning(data["early_warning"]),
        "spotlights_html": spot_html,
        "spotlights":      sp,
        "ai_rows": [
            {
                "ticker":     r["ticker"],
                "company":    r["company"],
                "price":      r["price"],
                "day_change": fmt_pct(r["day_change"]),
                "1_week":     fmt_pct(r["1_week"]),
                "1_month":    fmt_pct(r["1_month"]),
                "1_year":     fmt_pct(r["1_year"]),
                "52w_low":    r["52w_low"],
                "52w_high":   r["52w_high"],
                "beta":       r["beta"] if r["beta"] is not None else "N/A",
            }
            for r in data["ai_rows"]
        ],
        "why_paras":  narr.get("why_paras", []),
        "winners":    data["winners"],
        "losers":     data["losers"],
        "macro":      narr.get("macro", []),
        "earnings":   earnings_out,
        "econ":       [],
        "opportunity_radar": (
            "<ul>"
            + "".join(
                f"<li><strong>{r.get('theme')}</strong> — {r.get('why')} (e.g. {r.get('example')})</li>"
                for r in narr.get("opportunity_radar", [])
            )
            + f"</ul><p>{narr.get('portfolio_direction','')}</p>"
        ),
        "stw": stw,
    }


# ── Save ──────────────────────────────────────────────────────────────────────
def save_report(html, fe_json):
    ds = datetime.date.today().isoformat()
    for fn, content in [(f"report_{ds}.html", html), ("latest.html", html)]:
        with open(os.path.join(REPORTS_DIR, fn), "w", encoding="utf-8") as f:
            f.write(content)
    for fn in [f"report_{ds}.json", "latest.json"]:
        with open(os.path.join(REPORTS_DIR, fn), "w") as f:
            json.dump(fe_json, f, indent=2, default=str)
    idx_path = os.path.join(REPORTS_DIR, "index.json")
    try:
        with open(idx_path) as f:
            idx = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        idx = []
    if not any(r["file"] == f"report_{ds}.html" for r in idx):
        idx.insert(0, {
            "date": ds,
            "file": f"report_{ds}.html",
            "generated_at": datetime.datetime.now().isoformat(),
        })
    with open(idx_path, "w") as f:
        json.dump(idx[:30], f, indent=2)
    log.info(f"Saved report + JSON ({len(fe_json['ai_rows'])} AI rows, {len(fe_json['stw'])} STW)")


def generate_pdf(html, ds):
    try:
        from weasyprint import HTML, CSS
        p = os.path.join(REPORTS_DIR, f"report_{ds}.pdf")
        HTML(string=html).write_pdf(
            p, stylesheets=[CSS(string="@page{size:A4 landscape;margin:1.2cm}")]
        )
        return p
    except Exception as e:
        log.warning(f"PDF skipped: {e}")
        return None


def send_email(html, pdf=None):
    u, pw = os.getenv("GMAIL_ADDRESS"), os.getenv("GMAIL_APP_PASSWORD")
    if not u or not pw:
        raise EnvironmentError("GMAIL creds missing")
    label = datetime.date.today().strftime("%A, %B %d, %Y")
    msg   = MIMEMultipart("mixed")
    msg["Subject"] = f"Daily Market Report — {label}"
    msg["From"]    = f"{CONFIG['from_name']} <{u}>"
    msg["To"]      = ", ".join(CONFIG["to_emails"])
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(f"Daily market report for {label}. View in HTML.", "plain"))
    alt.attach(MIMEText(html, "html"))
    msg.attach(alt)
    if pdf:
        from email.mime.application import MIMEApplication
        with open(pdf, "rb") as f:
            att = MIMEApplication(f.read(), _subtype="pdf")
        att.add_header(
            "Content-Disposition", "attachment",
            filename=f"MarketReport_{datetime.date.today().isoformat()}.pdf",
        )
        msg.attach(att)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(u, pw)
        s.sendmail(u, CONFIG["to_emails"], msg.as_string())
    log.info(f"Email sent to {len(CONFIG['to_emails'])} recipients")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("Daily Market Report — starting")
    if datetime.date.today().weekday() == 6 and "--force" not in sys.argv:
        log.info("Sunday — skipping (use --force)")
        return

    mkt = get_market_context()
    log.info(mkt["context"])

    try:
        data = build_report_data()
        log.info(f"Data built: {len(data['ai_rows'])} AI rows, {len(data['spotlights'])} spotlights")

        fund_cache = {}
        for s in SPOTLIGHTS:
            fund_cache[s["symbol"]] = fundamentals_for(s["symbol"])
            time.sleep(4)
        log.info(f"Fundamentals fetched for {list(fund_cache.keys())}")

        narr = get_narrative(mkt, data)
        if not narr:
            log.warning("Empty narrative — rendering with numbers only")

        html    = render_email(mkt, data, narr, fund_cache)
        fe_json = build_frontend_json(mkt, data, narr, fund_cache)
        ds      = datetime.date.today().isoformat()
        save_report(html, fe_json)
        send_email(html, generate_pdf(html, ds))
        log.info("Completed ✓")

    except Exception as e:
        log.exception(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()