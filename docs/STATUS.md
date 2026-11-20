# Status

Last updated: 2026-11-20 (US time). Branch: `data` (browser-only site with latest prices).
Earlier, on request, the one-phase-at-a-time rule was set aside to build a first version of
three screens that span Phases 2, 2b and 4 (branch `three-screens`, merged).

## 2026-11-20: browser-only site with latest delayed prices (branch `data`)

Asked for: nothing on your computer; track, view and analyse everything in a web browser;
prices from a live free API (delayed is fine, accurate is required). Chosen: GitHub Pages
with a public repository, Yahoo Finance only (no API keys).

- **Latest delayed price** per watchlist stock and benchmark: Yahoo `regularMarketPrice`
  with its own `regularMarketTime`, checked (positive, not in the future, expected currency,
  move size, and after a close, agreement with the stored close within 0.5%), stored in
  `latest_quotes`, and shown on the stock list, stock detail and Data screen with its time
  in the market's zone. A failed refresh keeps the previous quote and says so. Indicators,
  scores and suggestions still use completed daily candles only.
- **Scheduled publishing** (`.github/workflows/publish-site.yml`): every 15 minutes during
  each market's session plus once a day, GitHub fetches candles and quotes, exports every
  screen, builds the static dashboard and deploys it to GitHub Pages (default branch only).
  The database is kept on the `market-data` branch between runs. This replaces the manual
  `fetch-data.yml` workflow.
- **The open page updates itself**: it checks for a newer build every two minutes and
  reloads the data. The header shows the last update time and warns when it is later than
  the schedule allows (60 minutes during a session, or more than a day).
- New API routes for the optional local app: `GET /api/quotes`, `POST /api/quotes/refresh`.

Verified by running:

- Backend: 166 tests pass (new: quote checks, quote service, provider parsing including
  yfinance 1.x's lazy metadata, API routes, export); `ruff`, `ruff format --check`,
  `mypy --strict` clean. Frontend: 17 tests, `eslint`, `tsc --noEmit`, production build clean.
- On GitHub Actions (push to `data`, 2026-11-20 19:41 UTC): 67 of 67 symbols' candles fetched
  and 44 of 44 latest prices fetched, 0 failed, no quote warnings. (The first run found every
  quote failing on yfinance 1.x's metadata type; fixed and re-run.)
- Accuracy spot check against news reports for 20 Nov 2026: the S&P 500's previous close
  implied by the quote (about 7,176) matches the reported Thursday close 8.2% below the
  7,818.93 record (about 7,178), and the day's moves (S&P 500 down about 2 to 3%, Nasdaq-100
  down about 4%, chip stocks down sharply) match the reports.
- The static site built from that real data opened in headless Chrome: Stocks and Data
  screens show the latest prices with their times.

Written but not run or not checked:

- The GitHub Pages deployment itself: it runs only from the default branch after the
  repository is public and Pages is set to GitHub Actions (see README). Not yet done.
- The scheduled (cron) runs: GitHub only runs schedules from the default branch.
- The open page noticing a newer build and reloading (logic is unit-tested in part only).

## What exists

Three screens you switch between, plus a Data screen, with a United States / India switch:

1. **Stocks**: 20 US and 20 Indian stocks with price history. Selecting one shows the
   rule-based suggestion (Buy candidate, Watch, No trade, Rejected), the score breakdown with
   its inputs, a trade plan (entry, stop, target, size, three scenarios), a place to record
   your own position (hold / exit / hedge advice, unrealised result, hedge estimate),
   stronger alternatives, and how the current strategy did on that stock.
2. **Risk analysis**: the current strategy (the spec's scoring model) backtested: results,
   chances over the next 20 trades, results split by volatility, market regime and period,
   harsher-conditions stress cases, and how large a loss can get.
3. **Strategies**: five alternative rule sets run under identical execution and compared
   with the current one, with return curves and what each says on the latest candle.

Ways to see it:

- **GitHub Pages site** (after the one-time setup in the README): updated by the scheduled
  job, nothing to run. Positions you enter are kept in that browser only.
- **Hosted snapshot** (a private page on claude.ai): read-only data frozen at export time,
  now superseded by the site. Positions you enter there are saved with the page.
- **The app itself** (README, optional): backend + frontend with manual refresh.

## Phase 1 exit criteria

| # | Criterion | State |
|---|---|---|
| 1 | Tests, linters, type checks pass | Verified |
| 2 | Real data fetched for every symbol and benchmark | **Verified on GitHub Actions**: 67 of 67 symbols fetched, 0 failed, about 5 years each. `^CNXMEDIA` returned only 1 row, so it is unusable (see limitations). |
| 3 | Backend and frontend run; pages show real data | Verified in the build environment using that real database (copied from the `market-data` branch). Not yet run on your own machine. |
| 4 to 6 | README, STATUS, small commits | Done |

## Verified by running

- Backend: 138 tests pass; `ruff`, `ruff format --check`, `mypy --strict` clean. New tests cover
  position sizing (hand-worked), the trade simulator (hand-built price paths: next-open fills,
  stops, gaps, targets, time and signal exits, costs), statistics and resampling, scoring,
  regime, suggestions, strategy rules, no look-ahead, and the new API routes end to end.
- Frontend: 10 tests, `eslint`, `tsc --noEmit`, production build clean.
- Real data: the `Fetch market data` workflow ran on GitHub and fetched all 67 symbols.
- All screens opened in headless Chrome from a static build fed with the real data.
- The snapshot export (`python -m app.export`) ran on the real database.

## Written but not run or not checked

- The hosted page itself could not be opened from the build environment. The identical build
  was checked locally, but saving positions through the hosted page's database is unverified.
- `docker compose up`: no Docker daemon was available.
- The app has not been run on your machine.
- The live "Refresh data now" button against Yahoo (Yahoo is blocked in the build environment;
  the same ingestion code ran successfully on GitHub Actions).

## Deviations from INSTRUCTIONS.md to know about

- **Several phases at once**, at your request. Each part is a first version, not a finished phase.
- **Arithmetic in the page for positions.** Positions live with the viewer (hosted page or
  browser), so quantity x price, unrealised result, sessions held and hedge value are computed
  in `frontend/src/positionMath.ts` (tested). Everything else is computed by the backend.
- **A `market-data` branch** holds the fetched SQLite file (public price candles only; no
  positions, no secrets). It exists so the hosted snapshot can be built. `data/` and `*.db`
  stay gitignored on code branches. Delete the branch if you would rather not keep it.
- **Example portfolio sizes** (10,000 USD and 500,000 INR) in `config/risk.yaml` drive the
  position-size illustrations. Replace them with your own.

## Known limitations

- Everything on the Risk and Strategies screens is a **BACKTEST** on past data. It does not
  predict results.
- **Survivorship bias**: the lists are today's large companies, which flatters past results.
- The score weights are the spec's untested starting values. Nothing was fitted, so there is
  no out-of-sample period; first-half and second-half results are shown instead.
- Probabilities come from resampling past trades and assume independence; real losses cluster.
- **No earnings dates or news.** Event risk inside the holding window is not checked, in
  suggestions or in backtests. The screens say so.
- Costs and slippage are estimates in `config/risk.yaml`.
- Per-trade statistics count every signal. "Return with limits" allows at most 4 positions at
  once and takes competing signals in date then alphabetical order.
- The per-stock size shown does not know your other holdings, so the sector and open-risk
  limits are applied as if the portfolio were empty.
- The 20-stock lists are a hand-picked selection of large companies, not a live ranking.
- Sector alignment: `^CNXMEDIA` (Communication Services, India) returned 1 row, so that
  component is unavailable for Bharti Airtel and its score uses the remaining weights.
- Indian sessions use the BSE calendar for NSE symbols; calendar mismatches appear as
  data-quality warnings. The library's Indian holiday data ends 2026-12-31.
- The claude.ai hosted snapshot does not update by itself; the GitHub Pages site does.
- **Indian calendar data ends 2026-12-31** in the installed `exchange_calendars`. The
  workflow installs the newest release on every run, so it recovers once the library
  publishes 2027 data; until then, Indian freshness and market status are unreliable from
  1 Jan 2027.
- Right after the Indian close, Yahoo's daily candle for that session can arrive with no
  close. It is rejected as a data-quality issue and those stocks show as stale until Yahoo
  fills it in on a later run; the latest price still shows.
- The site updates only as often as GitHub runs the schedule: runs can start late when
  GitHub is busy, and GitHub turns schedules off in a public repository after 60 days with
  no activity (re-enable from the Actions tab). The header warns when updates are late.
- Latest prices are delayed (Yahoo: about 15 minutes for many exchanges) and come from one
  source; there is no second source to cross-check them.
- On the GitHub Pages site, positions are kept per browser, not across devices.
- Suggestions use daily candles only and are rule outputs, not advice.
- yfinance is unofficial, delayed and can break without notice.
- `close` is split-adjusted by the provider; true unadjusted prices are not stored separately.

## Not built

Alerts, paper trading, portfolio-level risk across your real holdings,
correlation and concentration analysis, earnings and news, Settings screen, FX reporting,
a second price source for cross-checking, tuning or validating the score weights.

## Next steps (only when asked)

1. One-time setup (README): make the repository public, set Pages to GitHub Actions, merge
   `data` into `main`. Then confirm the site deploys and updates during a session.
2. Optional: add free Finnhub / Twelve Data keys as GitHub secrets to cross-check US prices.
3. Enter your real portfolio sizes in `config/risk.yaml`.
4. Add earnings dates (needs a data source decision) so event risk can be checked.
5. Scheduler and alerts (Phase 3).
