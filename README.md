# Short-Term Investment Intelligence

A personal decision-support dashboard for short-term (5 to 30 day) trades in US and Indian
equities. It has three screens:

1. **Stocks**: 20 US and 20 Indian stocks, each with price history, a rule-based suggestion,
   the reasoning behind it, a trade plan, and hold / exit / hedge advice for a position you record.
2. **Risk analysis**: a backtest of the current strategy with chances, failure conditions and
   worst-case losses.
3. **Strategies**: alternative strategies compared with the current one on the same data.

- **No live trading.** There are no broker connections and no order placement.
- Data comes from Yahoo Finance through `yfinance`: unofficial, free, **delayed / end-of-day**.
- **Scheduled monitoring is not active.** Data changes only when you run a refresh.
- Every performance number is a **BACKTEST**. A score is a ranking, not a probability.
- Not financial advice. The stock lists are a configurable selection, not recommendations.

Current progress and known limitations: [`docs/STATUS.md`](docs/STATUS.md).

## Requirements

Python 3.11+, Node 20+, and internet access to Yahoo Finance for refreshes. No API keys.

## Run locally

Backend (terminal 1):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m app.cli                 # first data fetch: 67 symbols, a few minutes
uvicorn app.main:app --reload --port 8000
```

Frontend (terminal 2):

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Open <http://localhost:5173>. "Refresh data now" on the Data screen runs the same fetch as
`python -m app.cli`. API docs: <http://localhost:8000/docs>.

`python -m app.cli --force` ignores the cache and re-downloads everything;
`python -m app.cli AAPL TCS.NS` limits the run to those symbols.

## Run with Docker

```bash
docker compose up --build
```

Dashboard at <http://localhost:5173>, API at <http://localhost:8000/api/health>. The SQLite file
is kept in `./data` (gitignored). Fetch data from the Data screen, or:

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
| `scoring.yaml` | Score weights, component scales, buy / watch / exit thresholds, rejection rules, regime rules |
| `risk.yaml` | Risk limits, example portfolio sizes, stop / target / holding rules, cost estimates, analysis settings |

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
| `GET /api/stocks` | Screen 1 list: score and suggestion for every watchlist stock |
| `GET /api/symbols/{symbol}/insight` | Screen 1 detail: score breakdown, plan, holder advice, hedge estimate |
| `GET /api/risk` | Screen 2: BACKTEST risk analysis of the current strategy |
| `GET /api/strategies` | Screen 3: BACKTEST strategy comparison |
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

## Hosted snapshot and fetching on GitHub

`.github/workflows/fetch-data.yml` fetches every configured symbol on a GitHub runner (run it
from the Actions tab or change `.github/fetch-trigger`). It keeps the SQLite file as a workflow
artifact and force-pushes it to the separate `market-data` branch (public price candles only).

To build a read-only snapshot of the screens from a database:

```bash
cd backend && python -m app.export ../snapshot-data          # JSON for every screen
cd ../frontend && VITE_STATIC=1 npx vite build --outDir ../site
cp -r ../snapshot-data ../site/data                           # then host the `site` folder
```

## Limitations

See [`docs/STATUS.md`](docs/STATUS.md) for the full list. The main ones: all results are
backtests on today's large companies (survivorship bias); earnings dates and news are not
available, so event risk is not checked; costs are estimates; yfinance can break without notice;
no scheduler, alerts or paper trading yet.

## Layout

```
backend/app/core/        pure logic: indicators, scoring, sizing, backtest, statistics, advice
backend/app/providers/   MarketDataProvider interface + YFinanceProvider
backend/app/services/    ingestion, calendars, analysis, research (the three screens)
backend/app/api/         FastAPI routes
backend/tests/           unit tests, synthetic fixtures, integration tests
frontend/                React + TypeScript dashboard (display only)
config/                  YAML settings
docs/STATUS.md           progress, verification, limitations, next steps
```
