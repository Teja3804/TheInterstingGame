import { createContext, useContext } from "react";
import type { Quote, QuotesResponse } from "./api";

/** The latest delayed prices, loaded once by the app and shared by every screen. */
export const QuotesContext = createContext<QuotesResponse | null>(null);

export function useQuote(symbol: string): Quote | undefined {
  const quotes = useContext(QuotesContext);
  for (const market of quotes?.markets ?? []) {
    const found = market.quotes.find((q) => q.symbol === symbol);
    if (found) return found;
  }
  return undefined;
}
