import { useEffect, useRef, useState, type ReactNode } from "react";
import { screens, SNAPSHOT } from "./api";
import { DataVersion, setCacheKey } from "./dataVersion";
import { QuotesContext } from "./quotes";
import { useLoad } from "./useLoad";

/** How often an open page checks whether a newer build of the site has been published. */
const CHECK_EVERY_MS = 2 * 60 * 1000;

// The first load of a published site skips any cached copy of the data files.
if (SNAPSHOT) setCacheKey(String(Date.now()));

/**
 * Shares the latest delayed prices with every screen and, on the published site, reloads all
 * data when the scheduled job has published a newer build.
 */
export function SiteData({ children }: { children: ReactNode }) {
  const [version, setVersion] = useState(0);
  const seen = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!SNAPSHOT) return;
    const check = () => {
      screens
        .statusFresh()
        .then((fresh) => {
          const exported = fresh.snapshot?.exported_at_utc;
          if (!exported || exported === seen.current) return;
          const first = seen.current === undefined;
          seen.current = exported;
          if (!first) {
            setCacheKey(exported);
            setVersion((v) => v + 1);
          }
        })
        .catch(() => {
          // Offline or a deploy in progress: try again at the next check.
        });
    };
    check();
    const timer = window.setInterval(check, CHECK_EVERY_MS);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <DataVersion.Provider value={version}>
      <QuotesLoader>{children}</QuotesLoader>
    </DataVersion.Provider>
  );
}

function QuotesLoader({ children }: { children: ReactNode }) {
  const quotes = useLoad(screens.quotes, "quotes");
  return <QuotesContext.Provider value={quotes.data}>{children}</QuotesContext.Provider>;
}
