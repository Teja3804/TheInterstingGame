// The published site is rebuilt on a schedule. When a newer build's data appears, the app
// bumps this version: every useLoad call reloads, and data requests carry the new key so
// browser and CDN caches cannot serve the old files.
import { createContext, useContext } from "react";

export const DataVersion = createContext(0);

let currentKey = "";

export function setCacheKey(key: string): void {
  currentKey = key;
}

export function cacheKey(): string {
  return currentKey;
}

export function useDataVersion(): number {
  return useContext(DataVersion);
}
