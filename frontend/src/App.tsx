import { NavLink, Route, Routes } from "react-router-dom";
import { Overview } from "./pages/Overview";
import { StockDetail } from "./pages/StockDetail";
import { Watchlist } from "./pages/Watchlist";

export function App() {
  return (
    <>
      <header className="masthead">
        <div className="masthead-row">
          <span className="wordmark">Short-Term Investment Intelligence</span>
          <nav aria-label="Pages">
            <NavLink to="/" end>
              Overview
            </NavLink>
            <NavLink to="/watchlist">Watchlist</NavLink>
          </nav>
        </div>
        <p className="standing-note">
          Prices are delayed end-of-day data from Yahoo Finance (yfinance, unofficial). Scheduled
          monitoring is not active: data changes only when you refresh it. Decision support only,
          not financial advice.
        </p>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/symbol/:symbol" element={<StockDetail />} />
          <Route path="*" element={<p className="notice">That page does not exist.</p>} />
        </Routes>
      </main>
    </>
  );
}
