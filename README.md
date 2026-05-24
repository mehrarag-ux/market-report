# 📈 Market Intelligence Dashboard

Daily AI-powered stock market report — auto-emailed and viewable in a browser dashboard.

## Repo Structure

```
market-dashboard/
├── frontend/
│   └── index.html          ← Dashboard UI (deploy to Vercel)
├── backend/
│   ├── market_report.py    ← Python script (runs on PythonAnywhere)
│   ├── requirements.txt
│   └── .env.example
├── vercel.json             ← Vercel deployment config
└── .gitignore
```

---

## Part 1 — Deploy Dashboard to Vercel

1. Push this repo to GitHub
2. Go to https://vercel.com → "Add New Project" → import your GitHub repo
3. Vercel auto-detects `vercel.json` and deploys `frontend/index.html`
4. Your dashboard is live at `https://your-project.vercel.app`

---

## Part 2 — Run the Email Script on PythonAnywhere

The `backend/market_report.py` script runs on PythonAnywhere and sends the daily email.

### Setup

```bash
pip install anthropic python-dotenv requests weasyprint
cp backend/.env.example backend/.env
# Fill in your keys in .env
```

### Credentials needed

| Variable | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com |
| `GMAIL_ADDRESS` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Google Account → Security → App Passwords |

### Run manually
```bash
python backend/market_report.py --force
```

### Cron schedule (PythonAnywhere Tasks)
```
22:00 UTC = 6:00 AM Singapore Time — weekdays only
```
Command: `python /home/mehrarag/market_report.py`

---

## Adding More Stocks

Edit the `watchlist` in `CONFIG` inside `market_report.py`:

```python
{"symbol": "NVDA", "name": "Nvidia", "type": "stock"},
{"symbol": "QQQ",  "name": "Invesco QQQ ETF", "type": "etf"},
```

---

## Using the Dashboard

1. Open your Vercel URL
2. Click **"Load Report File"**
3. Select any `report_YYYY-MM-DD.html` file from `backend/reports/`
4. The full report renders inside the dashboard

> Reports are saved locally in `backend/reports/` each time the script runs.
> They are excluded from Git via `.gitignore`.
