import { useCallback, useEffect, useState } from "react";
import { useDataVersion } from "./dataVersion";

export interface Loaded<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

export function useLoad<T>(load: () => Promise<T>, key: string): Loaded<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const version = useDataVersion();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    load()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : String(reason));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // `load` is recreated each render; `key` says when the request really changes, and
    // `version` when newer published data is available. Old data stays shown meanwhile.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick, version]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, error, loading, reload };
}
