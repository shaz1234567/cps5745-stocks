# CPS*5745 Stock Comparison Dashboard

Interactive Python dashboard comparing liquid US large-cap stocks with shared company and date-range filters.

**Author:** Shazab Ali  
**Course statement:** Developed for CPS*5745

## Tickers (default)

| Ticker | Why |
|--------|-----|
| **AAPL** | Consumer tech / iPhone ecosystem benchmark |
| **MSFT** | Enterprise software & cloud (Azure) peer |
| **GOOGL** | Digital advertising & search peer in Big Tech |

Optional extras in the multi-select: AMZN, NVDA, META.

## Charts (all driven by the same filters)

1. Indexed price (start of range = 100)
2. Daily percentage returns
3. Cumulative returns over the selected range
4. Trading volume (shares)
5. Rolling 20-day annualized volatility (%)

## Stack

- Dash + Plotly
- yfinance + pandas
- dash-bootstrap-components
- gunicorn (production)

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:8055](http://127.0.0.1:8055).

Override the port with `PORT=8055 python app.py`.

## Deploy (Render free web service)

1. Push this repo to GitHub/GitLab.
2. In [Render](https://render.com): **New → Blueprint** (uses `render.yaml`) or **Web Service**.
3. Build: `pip install -r requirements.txt`
4. Start: `gunicorn app:server --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
5. No secrets required. Public URL needs no sign-in.

## Notes

- Market data comes from Yahoo Finance via yfinance (auto-adjusted closes).
- Not investment advice.
