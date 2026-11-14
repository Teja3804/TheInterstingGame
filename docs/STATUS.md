# Status

Last updated: 2026-11-14. Current phase: **Phase 1 (built; real-data check still open)**.

## Phase 1 exit criteria

| # | Criterion | State |
|---|---|---|
| 1 | Tests, linters and type checks pass | **Verified** (see below) |
| 2 | Real data fetched for every watchlist symbol and benchmark | **Not done.** The build environment blocks Yahoo Finance (HTTP 403 from its network proxy), so all 17 symbols failed there for that reason. Must be run on a machine with normal internet access. |
| 3 | Backend and frontend run; all 3 pages show real data | **Partly.** Both run and all 3 pages render, checked with synthetic data only. Not yet seen with real data. |
| 4 | README has setup and run commands (local and Docker) | Done |
| 5 | This file lists features, limitations and next steps | Done |
| 6 | Work committed in small commits | Done |

**To close criteria 2 and 3** on your own machine:

```bash
cd backend && pip install -e ".[dev]"
pytest -m integration        # every configured symbol resolves on Yahoo Finance
python -m app.cli            # fetch 2 years for all 17 symbols; prints failures with reasons
```

Then start the app (README) and look at the three pages. Record the outcome here.

## Implemented

- **Scaffold:** backend, frontend, config, docs, tests, Docker files, GitHub Actions CI,
  `.gitignore`, `.env.example`, README.
- **Data layer:** `MarketDataProvider` interface and `YFinanceProvider`; SQLite storage unique on
  symbol + date + source with in-place updates; cache window; minimum delay between requests;
  retry with exponential backoff and an extra cooldown on rate limiting; response validation;
  missing-session, unexpected-session, zero-volume and suspicious-move detection; partial-candle
  exclusion; splits and dividends stored; full re-download when a new split **or dividend**
  appears; profile (name, sector, industry, exchange, currency); 2 years of history requested.
- **Watchlists and benchmarks** in `config/watchlists.yaml`.
- **Calendars and time zones** for US (`XNYS`) and India (`XBOM`) from `exchange_calendars`,
  used for market status, last completed session and freshness.
- **Indicators** (pure functions): SMA 20/50/200, EMA 9/21, RSI 14 (Wilder), MACD 12/26/9,
  ATR 14 (Wilder), Bollinger 20/2σ, relative volume vs the previous 20 sessions,
  1/5/10/20-session returns, relative strength vs the market's benchmark, annualised volatility,
  drawdown, confirmed swing-pivot support and resistance.
- **API:** the six Phase 1 routes, plus `python -m app.cli` for a manual refresh.
- **Dashboard:** Overview, Watchlist (US and India tabs) and Stock Detail.

## Verified by running

- `pytest`: 84 backend tests pass (2 integration tests deselected). They cover indicator maths
  against hand-calculated values and independent loop implementations, no look-ahead,
  insufficient history, data gaps, stale prices, stock splits, duplicate rows, partial-candle
  exclusion, time zones and daylight saving, holidays and early closes, provider retries, rate
  limiting and pacing, ingestion against a temporary SQLite database, and every API route.
- `ruff check`, `ruff format --check`, `mypy --strict`: clean.
- Frontend: `vitest` (5 tests), `eslint`, `tsc --noEmit` and `vite build`: clean.
- GitHub Actions CI ran on the `phase-1` branch and passed (backend and frontend jobs).
- Backend and frontend started together; the three pages were opened in headless Chrome against
  a throwaway database of **synthetic** candles (labelled as synthetic on screen), including a
  stale symbol and a symbol with no data.
- A real `python -m app.cli` run in the build environment: all 17 symbols failed with
  "CONNECT tunnel failed, response 403" and each failure was recorded and reported. Nothing was
  stored.

## Written but not run

- `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`: no
  Docker daemon was available.
- `YFinanceProvider` against the live Yahoo service, and the two integration tests. Its parsing,
  retries and pacing are tested only with a fake ticker.
- Whether every watchlist symbol and benchmark resolves on Yahoo (`^NSEBANK` and the `.NS`
  symbols in particular) is unconfirmed.

## Known limitations

- yfinance is unofficial, free and delayed; it can rate-limit or break without notice.
- `close` is split-adjusted by the provider, not the raw traded price. True unadjusted prices are
  not stored separately; they can be derived from `close` and the stored splits.
- NSE symbols use the BSE calendar (`XBOM`); `exchange_calendars` has no NSE calendar. Its Indian
  holiday data currently ends 2026-12-31. The Overview page shows the end date and warns when it
  is within 45 days.
- Calendar mismatches (for example special sessions) appear as "missing session" or "unexpected
  session" warnings rather than being resolved.
- A symbol listed for less than 2 years is fully re-downloaded on each refresh after the cache
  window.
- Relative strength is unavailable when the benchmark's latest candle differs from the stock's.
- Support and resistance are simple swing pivots, with no clustering or strength ranking.
- The manual refresh runs inside the HTTP request and should take roughly a minute for 17 symbols (estimated from the configured request delay, not measured).
- Profiles for indices and ETFs usually have no sector or industry; the page says so.
- Position-size maths and its test (listed under required test coverage) belong to the Phase 2
  trade planner and are not built yet.

## Not built (later phases)

Market regime, opportunity scoring, trade planner, position sizing, portfolio and risk limits,
alerts, scheduler, paper trading, backtesting, hedging, news, earnings dates, sector references.

## Next steps (Phase 2, only when asked)

1. Close Phase 1 criteria 2 and 3 with a real fetch.
2. Market regime classification with its evidence.
3. Explainable opportunity scoring and hard rejection rules (`config/scoring.yaml`).
4. Risk limits and position sizing with tests (`config/risk.yaml`).
5. Trade planner and Opportunity Scanner pages.
