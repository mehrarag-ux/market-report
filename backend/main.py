"""
Orchestrator: data -> LLM narrative -> render HTML + JSON -> save/email.
Numbers from data.py (Twelve Data + FRED). LLM writes narrative only.
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

C   = lambda v: "#1a7a3c" if (isinstance(v, (int, float)) and v >= 0) else "#c0392b"
TH  = 'style="background:#0a3d62;color:#fff;padding:8px;text-align:left;font-size:11px"'
TD  = 'style="padding:8px;border-bottom:1px solid #eee;font-size:13px"'
TBL = 'style="width:100%;border-collapse:collapse;font-size:13px;margin:12px 0"'
H2  = 'style="color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px"'


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


def render_macro_indicators(macro):
    if not macro:
        return ""
    rows = ""

    spread = macro.get("spread_10y2y")
    sc     = macro.get("spread_chg")
    if spread is not None:
        col   = "#c0392b" if macro.get("spread_inverted") else "#1a7a3c"
        label = "INVERTED" if macro.get("spread_inverted") else "NORMAL"
        chg   = f" ({sc:+.3f}pp)" if sc is not None else ""
        rows += (
            f"<tr><td {TD}><strong>2Y/10Y Spread</strong></td>"
            f"<td {TD}><span style='color:{col};font-weight:bold'>{spread:+.3f}%{chg}</span></td>"
            f"<td {TD}><span style='background:{col};color:#fff;padding:2px 8px;"
            f"border-radius:3px;font-size:11px'>{label}</span></td></tr>"
        )

    t5 = macro.get("tips_5y")
    if t5 is not None:
        flag = " (FLAG: diverging from 2% target)" if macro.get("tips_5y_flag") else ""
        rows += (
            f"<tr><td {TD}><strong>TIPS 5Y Breakeven</strong></td>"
            f"<td {TD}>{t5:.2f}%{flag}</td>"
            f"<td {TD}>Fed target: 2.0%</td></tr>"
        )

    t10 = macro.get("tips_10y")
    if t10 is not None:
        flag = " (FLAG: diverging from 2% target)" if macro.get("tips_10y_flag") else ""
        rows += (
            f"<tr><td {TD}><strong>TIPS 10Y Breakeven</strong></td>"
            f"<td {TD}>{t10:.2f}%{flag}</td>"
            f"<td {TD}>Fed target: 2.0%</td></tr>"
        )

    sofr  = macro.get("sofr")
    ff_lo = macro.get("ff_lower")
    ff_hi = macro.get("ff_upper")
    if sofr is not None:
        spike = macro.get("sofr_spike", False)
        col   = "#c0392b" if spike else "#333"
        note  = "SPIKE - above Fed Funds upper bound" if spike else (
            f"within target {ff_lo:.2f}%-{ff_hi:.2f}%" if (ff_lo and ff_hi) else ""
        )
        rows += (
            f"<tr><td {TD}><strong>SOFR</strong></td>"
            f"<td {TD}><span style='color:{col}'>{sofr:.4f}%</span></td>"
            f"<td {TD}>{note}</td></tr>"
        )

    dxy     = macro.get("dxy")
    dxy_chg = macro.get("dxy_chg")
    if dxy is not None:
        chg_html = span(dxy_chg) if dxy_chg is not None else ""
        rows += (
            f"<tr><td {TD}><strong>DXY Broad USD (weekly)</strong></td>"
            f"<td {TD}>{dxy:.2f} {chg_html}</td>"
            f"<td {TD}>DTWEXBGS — week-over-week change</td></tr>"
        )

    if not rows:
        return ""
    head = "".join(f"<th {TH}>{h}</th>" for h in ["Macro Indicator","Value","Signal / Note"])
    return f"<table {TBL}><tr>{head}</tr>{rows}</table>"


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
        'margin-top:8px;font-weight:bold">CORRECTION RISK - Consider reducing exposure or adding hedges</div>'
        if ew["correction_risk"] else ""
    )
    return (
        f"<table {TBL}><tr>{head}</tr>{rows}</table>"
        f"<p><strong>Overall: {ew['overall']}</strong></p>{warn}"
    )


def render_spotlight(s, narr, fund):
    n       = narr.get("spotlights", {}).get(s["ticker"], {})
    dc      = s.get("day_change")
    dc_html = span(dc) if dc is not None else '<span style="color:#888">N/A</span>'
    at      = n.get("analyst_target") or fund.get("target", "N/A")
    metrics = [
        ("Closing Price",  s.get("price")),
        ("Day Change",     dc_html),
        ("52W High",       s.get("hi52")),
        ("52W Low",        s.get("lo52")),
        ("P/E Ratio",      fund.get("pe",       "N/A")),
        ("Dividend Yield", fund.get("div",       "N/A")),
        ("Analyst View",   fund.get("analyst",   "N/A")),
        ("Analyst Target", at),
        ("Next Earnings",  fund.get("earnings",  "N/A")),
        ("Beta (1Y)",      s.get("beta")),
    ]
    body = "".join(
        f"<tr><td {TD}><strong>{k}</strong></td><td {TD}>{v}</td></tr>"
        for k, v in metrics
    )
    rating  = n.get("rating", "HOLD")
    verdict = n.get("verdict", "")
    return (
        f"<h3 style='color:#0a3d62'>{s['name']} ({s['ticker']})</h3>"
        f"<table {TBL}><tr><th {TH}>Metric</th><th {TH}>Value</th></tr>{body}</table>"
        f"<p><strong>{rating}</strong> - {verdict}</p>"
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
    rows = ""
    for s in SPOTLIGHTS:
        date = fund_cache.get(s["symbol"], {}).get("earnings", "N/A")
        rows += (
            f"<tr><td {TD}>{s['name']}</td><td {TD}>{s['symbol']}</td>"
            f"<td {TD}>{date}</td>"
            f"<td {TD}><span style='background:#0a3d62;color:#fff;padding:1px 6px;"
            f"border-radius:3px;font-size:10px'>WATCHLIST</span></td></tr>"
        )
    spotlight_syms = [s["symbol"] for s in SPOTLIGHTS]
    for e in (narr_earnings or []):
        if e.get("ticker") in spotlight_syms:
            continue
        rows += (
            f"<tr><td {TD}>{e.get('company','')}</td><td {TD}>{e.get('ticker','')}</td>"
            f"<td {TD}>{e.get('date','N/A')}</td><td {TD}></td></tr>"
        )
    head = "".join(f"<th {TH}>{h}</th>" for h in ["Company","Ticker","Next Earnings",""])
    return f"<table {TBL}><tr>{head}</tr>{rows}</table>"


def render_sector_opportunity_radar(sor):
    if not sor:
        return "<p>No sector opportunity data available.</p>"

    out = ""
    mc  = sor.get("macro_context", "")
    if mc:
        out += f"<p><strong>{mc}</strong></p>"

    themes = sor.get("themes", [])
    if themes:
        conv_col = {"HIGH": "#1a7a3c", "MEDIUM": "#f59e0b", "LOW": "#888"}
        head = "".join(
            f"<th {TH}>{h}</th>"
            for h in ["Sector","Theme","Opportunity Driver","Conviction","Time Horizon","Illustrative Names"]
        )
        body = ""
        for t in themes:
            c   = t.get("conviction", "MEDIUM").upper()
            col = conv_col.get(c, "#888")
            body += (
                f"<tr>"
                f"<td {TD}><strong>{t.get('sector','')}</strong></td>"
                f"<td {TD}>{t.get('theme','')}</td>"
                f"<td {TD}>{t.get('opportunity_driver','')}</td>"
                f"<td {TD}><span style='color:{col};font-weight:bold'>{c}</span></td>"
                f"<td {TD}>{t.get('time_horizon','')}</td>"
                f"<td {TD}><em>{t.get('illustrative_names','')}</em></td>"
                f"</tr>"
            )
        out += '<h3 style="color:#0a3d62;font-size:14px;margin-top:16px">Thematic Opportunity Table</h3>'
        out += f"<table {TBL}><tr>{head}</tr>{body}</table>"

    for dd in sor.get("deep_dives", []):
        out += (
            f'<h3 style="color:#0a3d62;font-size:14px;margin-top:20px">'
            f'Sector Deep Dive: {dd.get("sector","")}</h3>'
        )
        out += f"<p><strong>Sector Snapshot:</strong> {dd.get('snapshot','')}</p>"
        out += f"<p><strong>Why Today Matters:</strong> {dd.get('why_today','')}</p>"
        sub = dd.get("sub_industries", [])
        if sub:
            out += "<p><strong>Sub-Industry Conviction Ranking:</strong></p><ol>"
            for si in sub:
                out += (
                    f"<li><strong>{si.get('name','')} ({si.get('conviction','')})</strong> - "
                    f"{si.get('rationale','')} "
                    f"<em>Illustrative: {si.get('illustrative','')}</em></li>"
                )
            out += "</ol>"
        out += f"<p><strong>Key Risk:</strong> {dd.get('key_risk','')}</p>"

    return out


def render_market_trends(mt):
    if not mt:
        return "<p>No trend data available.</p>"
    up   = "".join(f"<li>{r}</li>" for r in mt.get("upside_risks", []))
    down = "".join(f"<li>{r}</li>" for r in mt.get("downside_risks", []))
    return (
        f"<p>{mt.get('commentary','')}</p>"
        f"<strong>Upside Risks</strong><ul>{up}</ul>"
        f"<strong>Downside Risks</strong><ul>{down}</ul>"
    )


def render_portfolio_allocation(pa):
    if not pa:
        return "<p>No allocation data available.</p>"
    head = "".join(f"<th {TH}>{h}</th>" for h in ["Bucket","Allocation %","Purpose"])
    rows = "".join(
        f"<tr><td {TD}><strong>{b.get('bucket','')}</strong></td>"
        f"<td {TD}>{b.get('allocation_pct','')}%</td>"
        f"<td {TD}>{b.get('purpose','')}</td></tr>"
        for b in pa.get("buckets", [])
    )
    trigger = pa.get("rebalance_trigger", "")
    return (
        f"<p>{pa.get('rationale','')}</p>"
        f"<table {TBL}><tr>{head}</tr>{rows}</table>"
        f"<p><strong>Rebalance Trigger:</strong> {trigger}</p>"
    )


def render_email(mkt, data, narr, fund_cache):
    h = (
        f'<div style="background:#0a3d62;color:#fff;padding:16px 20px;border-radius:6px;margin-bottom:24px">'
        f'<h1 style="margin:0;font-size:20px">Daily Market Report</h1>'
        f'<p style="margin:4px 0 0;font-size:13px;opacity:.85">'
        f'{mkt["last_trading_day"]} - After Market Close | Singapore</p></div>'
    )

    h += f'<h2 {H2}>SECTION 1 - Market Summary</h2>'
    h += render_indices(data["indices"])
    h += f'<p>{narr.get("pulse","")}</p>'
    h += render_macro_indicators(data.get("macro", {}))

    h += f'<h2 {H2}>SECTION 1B - Early Warning</h2>'
    h += render_early_warning(data["early_warning"])

    h += f'<h2 {H2}>SECTION 2 - Stock Spotlights</h2>'
    h += "".join(render_spotlight(s, narr, fund_cache.get(s["ticker"], {})) for s in data["spotlights"])

    h += f'<h2 {H2}>SECTION 3 - Watchlist</h2>'
    h += render_ai_table(data["ai_rows"])

    h += f'<h2 {H2}>SECTION 4 - Why Markets Moved</h2>'
    h += "".join(f"<p>{p}</p>" for p in narr.get("why_paras", []))

    win = "".join(f"<li>{w['name']}: {span_str(w['pct'])}</li>" for w in data["winners"])
    los = "".join(f"<li>{l['name']}: {span_str(l['pct'])}</li>" for l in data["losers"])
    mac = "".join(f"<li>{m}</li>" for m in narr.get("macro", []))
    h += (
        f'<h2 {H2}>SECTION 5 - Sector Rotation & Macro</h2>'
        f'<strong>Winners</strong><ul>{win}</ul>'
        f'<strong>Losers</strong><ul>{los}</ul>'
        f'<strong>Macro</strong><ul>{mac}</ul>'
    )

    h += (
        f'<h2 {H2}>SECTION 6 - Earnings Calendar</h2>'
        f'<p style="font-size:11px;color:#888;margin-bottom:8px">'
        f'Watchlist stocks verified. Broader NDX dates sourced via web search - confirm before trading.</p>'
        + render_earnings(narr.get("earnings_calendar", []), fund_cache)
    )

    radar = "".join(
        f"<li><strong>{r.get('theme')}</strong> - {r.get('why')} (e.g. {r.get('example')})</li>"
        for r in narr.get("opportunity_radar", [])
    )
    h += (
        f'<h2 {H2}>SECTION 6B - Opportunity Radar</h2>'
        f'<ul>{radar}</ul><p>{narr.get("portfolio_direction","")}</p>'
    )

    h += f'<h2 {H2}>SECTION 7 - Sector Opportunity Radar</h2>'
    h += render_sector_opportunity_radar(narr.get("sector_opportunity_radar", {}))

    h += f'<h2 {H2}>SECTION 8 - Market Trends</h2>'
    h += render_market_trends(narr.get("market_trends"))

    h += f'<h2 {H2}>SECTION 9 - Portfolio Allocation (5-8 Year Horizon)</h2>'
    h += render_portfolio_allocation(narr.get("portfolio_allocation"))

    h += (
        '<p style="font-size:11px;color:#888;border-top:1px solid #eee;'
        'padding-top:12px;margin-top:32px">Auto-generated. Prices from public market data; '
        'commentary AI-generated. Not financial advice.</p>'
    )
    return h


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
    fmt_pct = lambda v: f"{v:+.2f}%" if v is not None else "-"

    earnings_out = [
        {"company": s["name"], "ticker": s["symbol"], "date": fund_cache.get(s["symbol"], {}).get("earnings", "N/A")}
        for s in SPOTLIGHTS
    ]
    spotlight_tickers = {s["symbol"] for s in SPOTLIGHTS}
    for e in (narr.get("earnings_calendar") or []):
        if e.get("ticker") not in spotlight_tickers:
            earnings_out.append(e)

    sor_html = render_sector_opportunity_radar(narr.get("sector_opportunity_radar", {}))

    return {
        "date":      mkt["last_trading_day_iso"],
        "generated": datetime.datetime.now().isoformat(),
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
        "pulse":             narr.get("pulse", ""),
        "macro_indicators":  data.get("macro", {}),
        "early_warning":     render_early_warning(data["early_warning"]),
        "spotlights_html":   spot_html,
        "spotlights":        sp,
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
        "why_paras": narr.get("why_paras", []),
        "winners":   data["winners"],
        "losers":    data["losers"],
        "macro":     narr.get("macro", []),
        "earnings":  earnings_out,
        "econ":      [],
        "opportunity_radar": (
            "<ul>"
            + "".join(
                f"<li><strong>{r.get('theme')}</strong> - {r.get('why')} (e.g. {r.get('example')})</li>"
                for r in narr.get("opportunity_radar", [])
            )
            + f"</ul><p>{narr.get('portfolio_direction','')}</p>"
        ),
        "sector_opportunity_radar": sor_html,
        "market_trends":            render_market_trends(narr.get("market_trends")),
        "portfolio_allocation":     render_portfolio_allocation(narr.get("portfolio_allocation")),
    }


def save_report(html, fe_json, ds):
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
        idx.insert(0, {"date": ds, "file": f"report_{ds}.html", "generated_at": datetime.datetime.now().isoformat()})
    with open(idx_path, "w") as f:
        json.dump(idx[:30], f, indent=2)
    log.info("Saved report + JSON")


def generate_pdf(html, ds):
    try:
        from weasyprint import HTML, CSS
        p = os.path.join(REPORTS_DIR, f"report_{ds}.pdf")
        HTML(string=html).write_pdf(p, stylesheets=[CSS(string="@page{size:A4 landscape;margin:1.2cm}")])
        return p
    except Exception as e:
        log.warning(f"PDF skipped: {e}")
        return None


def send_email(html, mkt, pdf=None):
    u, pw = os.getenv("GMAIL_ADDRESS"), os.getenv("GMAIL_APP_PASSWORD")
    if not u or not pw:
        raise EnvironmentError("GMAIL creds missing")
    label = mkt["last_trading_day"]
    msg   = MIMEMultipart("mixed")
    msg["Subject"] = f"Daily Market Report - {label}"
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
        att.add_header("Content-Disposition", "attachment", filename=f"MarketReport_{mkt['last_trading_day_iso']}.pdf")
        msg.attach(att)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(u, pw)
        s.sendmail(u, CONFIG["to_emails"], msg.as_string())
    log.info(f"Email sent to {len(CONFIG['to_emails'])} recipients")


def main():
    log.info("=" * 60)
    log.info("Daily Market Report - starting")
    if datetime.date.today().weekday() == 6 and "--force" not in sys.argv:
        log.info("Sunday - skipping (use --force)")
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
            log.warning("Empty narrative - rendering with numbers only")

        html    = render_email(mkt, data, narr, fund_cache)
        fe_json = build_frontend_json(mkt, data, narr, fund_cache)
        ds      = mkt["last_trading_day_iso"]
        save_report(html, fe_json, ds)
        send_email(html, mkt, generate_pdf(html, ds))
        log.info("Completed")

    except Exception as e:
        log.exception(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()