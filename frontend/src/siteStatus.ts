import type { StatusResponse } from "./api";

/** The scheduled job also runs once a day, so an update older than this means it stopped. */
export const DAILY_LIMIT_MINUTES = 26 * 60;

/**
 * Whether the published data is older than the schedule allows. Display logic only: it
 * compares the build time with the clock of the viewer's device.
 */
export function updateIsLate(status: StatusResponse | null, now: number): boolean {
  const snap = status?.snapshot;
  if (!snap?.scheduled) return false;
  const age = (now - Date.parse(snap.exported_at_utc)) / 60000;
  const openAtUpdate = status?.markets.some((m) => m.clock.is_open) ?? false;
  const limit = snap.stale_after_minutes ?? Infinity;
  return age > DAILY_LIMIT_MINUTES || (openAtUpdate && age > limit);
}
