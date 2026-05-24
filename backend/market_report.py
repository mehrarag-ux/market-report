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
import anthropic

load_dotenv()

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
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

# CONFIGURATION — Edit this section to customise your report
CONFIG = {
    "to_email": "mehrarag@gmail.com",
    "from_name": "Daily Market Report",
    "watchlist": [
        {"symbol": "SPX",  "name": "S&P 500 Index", "type": "index"},
        {"symbol": "NDX",  "name": "Nasdaq 100",    "type": "index"},
        {"symbol": "C",    "name": "Citigroup",     "type": "stock"},
        {"symbol": "QRVO", "name": "Qorvo",         "type": "stock"},
        # Add more stocks below:
        # {"symbol": "NVDA", "name": "Nvidia",       "type": "stock"},
        # {"symbol": "QQQ",  "name": "Invesco QQQ",  "type": "etf"},
    ],
    "claude_model": "claude-haiku-4-5-20251001",
    "max_tokens": 4096,
}


def is_weekday():
    return datetime.datetime.now().weekday() < 5


def build_prompt_part1():
    today = datetime.datetime.now().strftime("%A, %B %d, %Y")
    prompt = "You are a financial analyst writing a daily after-market-close report for a retail investor in Singapore."
    prompt += " Today is " + today + ". The US stock market has just closed for the day."
    prompt += " Search the web for todays actual closing data and write ONLY these two sections:"

    prompt += " SECTION 1 - Market Summary:"
    prompt += " Search for todays closing prices for S&P 500 and Nasdaq 100 index ticker NDX."
    prompt += " Search for these one at a time to find historical performance data:"
    prompt += " First search: S&P 500 weekly performance this week percentage."
    prompt += " Second search: S&P 500 monthly return " + datetime.datetime.now().strftime("%B %Y") + "."
    prompt += " Third search: Nasdaq 100 NDX weekly return this week."
    prompt += " Fourth search: Nasdaq 100 NDX monthly performance " + datetime.datetime.now().strftime("%B %Y") + "."
    prompt += " Fifth search: S&P 500 return past 12 months " + datetime.datetime.now().strftime("%Y") + "."
    prompt += " Sixth search: Nasdaq 100 NDX annual return " + datetime.datetime.now().strftime("%Y") + "."
    prompt += " Use the numbers you find to fill 1 Week, 1 Month, 1 Year columns."
    prompt += " If you cannot find a percentage change directly, search for the price from 1 week ago and 1 month ago and calculate the percentage difference yourself."
    prompt += " Only write Unavailable if you have searched at least 3 times and truly cannot find the data."
    prompt += " Write a clear HTML table with columns: Index, Closing Price, Day Change, 1 Week, 1 Month, 1 Year, 52W High, 52W Low."
    prompt += " Also include VIX level and what it means for investors in one sentence."
    prompt += " Below the table write 2 sentences in plain English summarising how the market performed today and why."

    prompt += " SECTION 2 - Stock Spotlights:"
    prompt += " Search for Citigroup stock ticker C - todays closing price, day change, todays day low price, todays day high price, 52 week high and low, P/E ratio, analyst buy hold sell consensus, price target, next earnings date, and any news today."
    prompt += " Present these in a clear HTML table with two columns: Metric and Value."
    prompt += " Give a clear BUY HOLD or SELL recommendation with 3 sentences explaining why in plain English."
    prompt += " Search for Qorvo stock ticker QRVO - same data points as Citigroup including todays day low and day high."
    prompt += " Present these in a clear HTML table with two columns: Metric and Value."
    prompt += " Give a clear BUY HOLD or SELL recommendation with 3 sentences explaining why in plain English."

    prompt += " IMPORTANT RULES:"
    prompt += " Always search for real data before writing. Never make up numbers."
    prompt += " Always refer to Nasdaq index as Nasdaq 100 throughout."
    prompt += " Write everything in plain simple English that a non-expert investor can understand."
    prompt += " Format output as clean HTML for email using Arial font, dark blue headings, green for positive numbers, red for negative numbers."
    prompt += " Use this wrapper: <div style=font-family:Arial,sans-serif;max-width:620px;margin:0 auto;padding:20px;color:#1a1a1a;line-height:1.6>"
    prompt += " Use this for headings: <h2 style=color:#0a3d62;font-size:16px;border-bottom:2px solid #0a3d62;padding-bottom:4px;margin-top:28px>"
    prompt += " For tables: <table style=width:100%;border-collapse:collapse;font-size:13px;margin:12px 0>"
    prompt += " For positive numbers: <span style=color:#1a7a3c;font-weight:bold>"
    prompt += " For negative numbers: <span style=color:#c0392b;font-weight:bold>"
    prompt += " Start with: <div style=background:#0a3d62;color:#ffffff;padding:16px 20px;border-radius:6px;margin-bottom:24px><h1 style=margin:0;font-size:20px>Daily Market Report</h1><p style=margin:4px 0 0;font-size:13px;opacity:0.85>" + today + " - After Market Close</p></div>"
    return prompt


def build_prompt_part2():
    today = datetime.datetime.now().strftime("%A, %B %d, %Y")
    tickers = ", ".join(f"{w['symbol']} ({w['name']})" for w in CONFIG["watchlist"])

    prompt = "You are a financial analyst writing part 2 of a daily after-market-close report for a retail investor in Singapore."
    prompt += " Today is " + today + ". Search the web for todays actual market data and write ONLY these sections:"

    prompt += " SECTION 3 - Watchlist Performance Table:"
    prompt += " This section MUST appear first before any other section in your response."
    prompt += " Search for each of these tickers one at a time: " + tickers
    prompt += " For each ticker search for: closing price, day change percent, 1 week change, 1 month change, 1 year change, 52 week low, 52 week high."
    prompt += " If you cannot find a percentage change directly, find the price from 1 week or 1 month ago and calculate it yourself."
    prompt += " Present in a clear HTML table with columns: Name, Price, Day Change, 1 Week, 1 Month, 1 Year, 52W Low, 52W High."
    prompt += " Use green for positive numbers and red for negative numbers."
    prompt += " Only write Unavailable if you truly cannot find the number after searching twice."

    prompt += " SECTION 4 - Why Markets Moved Today:"
    prompt += " Search for the main reasons US markets moved today."
    prompt += " Always refer to Nasdaq index as Nasdaq 100 throughout this section."
    prompt += " Write 3 paragraphs in plain English explaining what happened and why it matters to investors."
    prompt += " Name specific stocks, events, Fed news, economic data, or geopolitical events that drove the market."

    prompt += " SECTION 5 - Sector Rotation and Macro Highlights:"
    prompt += " Search for which sectors gained and which sectors fell today."
    prompt += " List top 3 winning sectors and top 2 losing sectors with percentage moves."
    prompt += " Include 3 bullet points on important macro news today such as Fed statements, inflation data, jobs data, oil prices."
    prompt += " Explain each in one simple sentence."

    prompt += " SECTION 6 - Earnings and Economic Calendar:"
    prompt += " Keep this section SHORT and concise."
    prompt += " Search for earnings reports due in the next 5 days and list the top 5 most important ones with date and company name only."
    prompt += " Search for economic data releases due this week and list the top 3 most important ones with date and one sentence explanation."

    prompt += " SECTION 7 - Stocks to Watch:"
    prompt += " Based on todays market activity and news, list exactly 3 stocks worth watching."
    prompt += " You MUST include exactly 1 BUY, 1 HOLD, and 1 SELL."
    prompt += " For the BUY stock: recommend a stock suitable for long term investment with a 5 year horizon. Explain why it has strong long term growth potential over 5 years in 2 sentences."
    prompt += " For the HOLD stock: recommend a stock suitable for holding over a 1 year horizon. Explain why it is worth holding for the next 12 months but not necessarily a long term pick in 2 sentences."
    prompt += " For the SELL stock: recommend a stock that should be sold immediately with no holding period. Explain clearly why an investor should exit this position now in 2 sentences."
    prompt += " For each stock write: name, ticker, current price, rating with time horizon, and the 2 sentence explanation."
    prompt += " Keep this section brief and focused."

    prompt += " IMPORTANT RULES:"
    prompt += " Always search for real data. Never make up numbers."
    prompt += " Always write Nasdaq 100 not Nasdaq Composite."
    prompt += " Write everything in plain simple English."
    prompt += " Format as clean HTML using Arial font, dark blue headings, green for positive numbers, red for negative numbers."
    prompt += " End with: <p style=font-size:11px;color:#888;border-top:1px solid #eee;padding-top:12px;margin-top:32px>This report is auto-generated by Claude AI for informational purposes only. Not financial advice.</p>"
    return prompt


def generate_report(client):
    log.info("Generating Part 1 - Market Summary and Spotlights...")
    response1 = client.messages.create(
        model=CONFIG["claude_model"],
        max_tokens=CONFIG["max_tokens"],
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": build_prompt_part1()}],
    )
    html1 = ""
    for block in response1.content:
        if hasattr(block, "text") and block.text.strip():
            html1 += block.text
    log.info("Part 1 done - " + str(len(html1)) + " characters")

    log.info("Generating Part 2 - Watchlist and Commentary...")
    response2 = client.messages.create(
        model=CONFIG["claude_model"],
        max_tokens=CONFIG["max_tokens"],
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": build_prompt_part2()}],
    )
    html2 = ""
    for block in response2.content:
        if hasattr(block, "text") and block.text.strip():
            html2 += block.text
    log.info("Part 2 done - " + str(len(html2)) + " characters")

    html = html1 + "\n<br>\n" + html2
    log.info("Full report ready - " + str(len(html)) + " characters")
    return html


def save_report(html):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    html_path = os.path.join(REPORTS_DIR, f"report_{date_str}.html")
    json_path = os.path.join(REPORTS_DIR, f"report_{date_str}.json")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    log.info("HTML report saved to " + html_path)

    # Save JSON metadata for dashboard
    meta = {
        "date": date_str,
        "generated_at": datetime.datetime.now().isoformat(),
        "html_file": f"report_{date_str}.html",
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)

    # Save PDF
    pdf_path = os.path.join(REPORTS_DIR, f"report_{date_str}.pdf")
    try:
        from weasyprint import HTML, CSS
        css = CSS(string="@page { size: A4 landscape; margin: 1.5cm; }")
        HTML(string=html).write_pdf(pdf_path, stylesheets=[css])
        log.info("PDF saved to " + pdf_path)
    except Exception as e:
        log.warning("PDF generation failed - " + str(e))
        pdf_path = None

    return html_path, pdf_path


def send_email(html_body, pdf_path=None):
    smtp_user = os.getenv("GMAIL_ADDRESS")
    smtp_pass = os.getenv("GMAIL_APP_PASSWORD")
    if not smtp_user or not smtp_pass:
        raise EnvironmentError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in .env file.")
    today_label = datetime.datetime.now().strftime("%A, %B %d, %Y")
    subject = "Daily Market Report - " + today_label
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = CONFIG["from_name"] + " <" + smtp_user + ">"
    msg["To"] = CONFIG["to_email"]
    alt_part = MIMEMultipart("alternative")
    plain = "Your daily market report for " + today_label + ". Please view in an HTML email client."
    alt_part.attach(MIMEText(plain, "plain"))
    alt_part.attach(MIMEText(html_body, "html"))
    msg.attach(alt_part)
    if pdf_path:
        try:
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()
            pdf_att = MIMEApplication(pdf_data, _subtype="pdf")
            pdf_name = "Market_Report_" + datetime.datetime.now().strftime("%Y-%m-%d") + ".pdf"
            pdf_att.add_header("Content-Disposition", "attachment", filename=pdf_name)
            msg.attach(pdf_att)
            log.info("PDF attached to email")
        except Exception as e:
            log.warning("Could not attach PDF - " + str(e))
    log.info("Connecting to Gmail SMTP...")
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(smtp_user, smtp_pass)
    server.sendmail(smtp_user, CONFIG["to_email"], msg.as_string())
    server.quit()
    log.info("Email sent to " + CONFIG["to_email"])


def main():
    log.info("Daily Market Report - starting")
    if not is_weekday() and "--force" not in sys.argv:
        log.info("Today is a weekend. Skipping. Use --force to override.")
        return
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not found in .env file.")
    client = anthropic.Anthropic(api_key=api_key)
    try:
        html = generate_report(client)
        html_path, pdf_path = save_report(html)
        send_email(html, pdf_path)
        log.info("Daily Market Report - completed successfully")
    except Exception as exc:
        log.exception("Report failed - " + str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
