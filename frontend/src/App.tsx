import { useEffect, useState } from "react";
import { screens, SNAPSHOT } from "./api";
import { formatInstant } from "./format";
import { DataStatus } from "./pages/DataStatus";
import { Risk } from "./pages/Risk";
import { Stocks } from "./pages/Stocks";
import { Strategies } from "./pages/Strategies";
import { useLoad } from "./useLoad";

const VIEWS = [
  ["stocks", "Stocks"],
  ["risk", "Risk analysis"],
  ["strategies", "Strategies"],
  ["data", "Data"],
] as const;
type View = (typeof VIEWS)[number][0];

const MARKETS = [
  ["US", "United States"],
  ["IN", "India"],
] as const;
export type MarketCode = (typeof MARKETS)[number][0];

function viewFromHash(): View {
  const name = window.location.hash.replace("#", "");
  return VIEWS.some(([key]) => key === name) ? (name as View) : "stocks";
}

export function App() {
  const [view, setView] = useState<View>(viewFromHash);
  const [market, setMarket] = useState<MarketCode>("US");
  const status = useLoad(screens.status, "status");

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = (next: View) => {
    window.location.hash = next;
    setView(next);
  };
  const exported = status.data?.snapshot?.exported_at_utc;
  const zone = market === "US" ? "America/New_York" : "Asia/Kolkata";

  return (
    <div className={`app market-${market}`}>
      <header className="masthead">
        <div className="masthead-row">
          <span className="wordmark">Short-Term Investment Intelligence</span>
          <nav aria-label="Screens">
            {VIEWS.map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={key === view ? "nav-item active" : "nav-item"}
                aria-current={key === view ? "page" : undefined}
                onClick={() => go(key)}
              >
                {label}
              </button>
            ))}
          </nav>
          <div className="market-switch" role="group" aria-label="Market">
            {MARKETS.map(([code, label]) => (
              <button
                key={code}
                type="button"
                className={code === market ? `switch switch-${code} active` : `switch switch-${code}`}
                aria-pressed={code === market}
                onClick={() => setMarket(code)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <p className="standing-note">
          {SNAPSHOT
            ? `Read-only snapshot${exported ? ` taken ${formatInstant(exported, zone)}` : ""}. It does not update by itself. `
            : "Scheduled monitoring is not active: data changes only when you refresh it. "}
          Prices are delayed end-of-day data from Yahoo Finance (yfinance, unofficial). Decision
          support only, not financial advice. This tool never places orders.
        </p>
      </header>
      <main key={view} className="view">
        {view === "stocks" && <Stocks market={market} />}
        {view === "risk" && <Risk market={market} />}
        {view === "strategies" && <Strategies market={market} />}
        {view === "data" && <DataStatus />}
      </main>
    </div>
  );
}
