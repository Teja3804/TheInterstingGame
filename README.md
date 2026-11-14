# Short-Term Investment Intelligence

A personal decision-support dashboard for short-term (5 to 30 day) trades in US and Indian
equities. **Phase 1** stores daily price history, computes technical indicators and shows them
on three pages: Overview, Watchlist and Stock Detail.

- **No live trading.** There are no broker connections and no order placement.
- Data comes from Yahoo Finance through `yfinance`: unofficial, free, **delayed / end-of-day**.
- **Scheduled monitoring is not active.** Data changes only when you run a manual refresh.
- Not financial advice. The watchlist is a demonstration, not a set of recommendations.

Current progress and known limitations: [`docs/STATUS.md`](docs/STATUS.md).

## Requirements

Python 3.11+, Node 20+, and internet access to Yahoo Finance for refreshes. No API keys.

## Run locally

Backend (terminal 1):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m app.cli                 # first data fetch: 17 symbols
uvicorn app.main:app --reload --port 8000
```

Frontend (terminal 2):

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Open <http://localhost:5173>. "Refresh data now" on the Overview page runs the same fetch as
`python -m app.cli`. API docs: <http://localhost:8000/docs>.

`python -m app.cli --force` ignores the cache and re-downloads everything;
`python -m app.cli AAPL TCS.NS` limits the run to those symbols.

## Run with Docker

```bash
docker compose up --build
```

Dashboard at <http://localhost:5173>, API at <http://localhost:8000/api/health>. The SQLite file
is kept in `./data` (gitignored). Fetch data from the Overview page, or:

```bash
docker compose exec backend python -m app.cli
```

## Test and check

```bash
cd backend
pytest                      # unit tests, synthetic fixtures only, no network
pytest -m integration       # live checks against Yahoo Finance (needs network)
ruff check . && ruff format --check . && mypy

cd ../frontend
npm test && npm run lint && npm run typecheck
```

CI (`.github/workflows/ci.yml`) runs all of the above except the integration tests on every push.

## Configuration

Everything tunable is in `config/`:

| File | Contents |
|---|---|
| `watchlists.yaml` | Markets, time zones, currencies, calendars, symbols and benchmarks |
| `settings.yaml` | Provider pacing and retries, cache times, close buffer, data-quality thresholds, indicator parameters |
| `risk.yaml`, `scoring.yaml` | Empty until Phase 2 |

Optional environment variables are listed in `.env.example` (`STI_DATABASE_URL`,
`STI_CONFIG_DIR`, `STI_CORS_ORIGINS`). Never commit `.env`.

## API

| Route | Purpose |
|---|---|
| `GET /api/health` | Liveness, and that no scheduler is running |
| `GET /api/sources/status` | Market clocks, freshness counts, per-symbol fetch status |
| `GET /api/watchlists` | Watchlist rows with indicators, per market |
| `GET /api/symbols/{symbol}/prices` | Stored daily candles (`?sessions=N`) |
| `GET /api/symbols/{symbol}/indicators` | Indicator snapshot and series, support/resistance, warnings, profile |
| `POST /api/ingest` | Manual refresh (`{"symbols": [...], "force": false}`, both optional) |

## How prices are handled

- Only **completed** daily candles are stored. Today's bar is dropped until the session's close
  plus 30 minutes has passed.
- `close` is split-adjusted as Yahoo reports it; `adj_close` is also dividend-adjusted. Both are
  stored, with splits and dividends in their own table. **Indicators and the chart use adjusted
  prices**; the "last close" figure is `close`.
- When a new split or dividend appears, the symbol's whole history is downloaded again, because
  adjusted prices change retroactively.
- Times are stored in UTC and shown in America/New_York (US) or Asia/Kolkata (India). USD and INR
  figures are never combined.
- Fresh = the latest stored candle is the last completed session on that market's calendar.
  Stale = a newer session has completed. Weekends and holidays never count as stale.

## Limitations

- yfinance is unofficial and can rate-limit, change or break without notice. It is never real-time.
- Daily candles only; no intraday data.
- Indian sessions use the BSE calendar (`XBOM`) from `exchange_calendars` for NSE symbols too.
  That library's Indian holiday data ends on a fixed date, which the Overview page shows.
- Phase 1 has no scoring, market regime, trade planning, portfolio, alerts, scheduler,
  backtesting, news or earnings dates. See `docs/STATUS.md`.

## Layout

```
backend/app/core/        pure logic: indicators, data-quality checks, freshness
backend/app/providers/   MarketDataProvider interface + YFinanceProvider
backend/app/services/    ingestion, calendars, analysis
backend/app/api/         FastAPI routes
backend/tests/           unit tests, synthetic fixtures, integration tests
frontend/                React + TypeScript dashboard (display only)
config/                  YAML settings
docs/STATUS.md           progress, verification, limitations, next steps
```
