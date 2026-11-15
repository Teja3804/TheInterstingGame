# Test fixtures

Every CSV here is **synthetic**. None of it is real market data.

- `synthetic_daily.csv`, `synthetic_benchmark.csv`, `synthetic_split.csv`: seeded random walks
  written by `make_fixtures.py`.
- `hand_calculated.csv`: seven small candles whose indicator values are worked out by hand in
  `tests/test_indicators.py`.

Lines starting with `#` are comments (`pd.read_csv(..., comment="#")`).
