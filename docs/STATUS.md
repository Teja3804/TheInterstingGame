# Status

Last updated: 2026-11-14 (US time). On request, the one-phase-at-a-time rule was set aside to
build a first version of three screens that span Phases 2, 2b and 4. Branch: `three-screens`.

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

Two ways to see it:

- **Hosted snapshot** (a private page on claude.ai): read-only data frozen at export time.
  Positions you enter there are saved with the page.
- **The app itself** (README): backend + frontend with live refresh.

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
- The hosted snapshot does not update by itself. Refreshing it needs a new fetch and export.
- Suggestions use daily candles only and are rule outputs, not advice.
- yfinance is unofficial, delayed and can break without notice.
- `close` is split-adjusted by the provider; true unadjusted prices are not stored separately.

## Not built

Scheduler and alerts, paper trading, portfolio-level risk across your real holdings,
correlation and concentration analysis, earnings and news, Settings screen, FX reporting,
automatic refresh of the hosted snapshot, tuning or validating the score weights.

## Next steps (only when asked)

1. Open the hosted page and confirm saving a position works; run the app on your machine.
2. Decide whether to keep the `market-data` branch and whether to schedule regular refreshes.
3. Enter your real portfolio sizes in `config/risk.yaml`.
4. Add earnings dates (needs a data source decision) so event risk can be checked.
5. Scheduler and alerts (Phase 3).
