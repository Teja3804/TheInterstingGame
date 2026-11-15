// Positions the user enters by hand. This app never talks to a broker.
//
// Hosted page: saved with the page's own database, so they follow the user across
// devices. Elsewhere: saved in this browser only. Either way they never enter git.

export interface Position {
  id: string;
  symbol: string;
  quantity: number;
  entry_price: number;
  entry_date: string; // YYYY-MM-DD
}

export type StoreKind = "hosted" | "browser" | "memory";

export interface PositionStore {
  kind: StoreKind;
  subscribe(listener: (positions: Position[]) => void): () => void;
  save(position: Position): Promise<void>;
  remove(id: string): Promise<void>;
}

// The hosted runtime's document store (only the parts used here).
interface HostedDoc {
  set(data: Record<string, unknown>): Promise<void>;
  delete(): Promise<void>;
}
interface HostedSnapshot {
  docs: { id: string; data(): Record<string, unknown> | undefined }[];
}
interface HostedDb {
  collection(path: string): {
    doc(id?: string): HostedDoc;
    onSnapshot(next: (snap: HostedSnapshot) => void, error?: (e: unknown) => void): () => void;
  };
}
declare global {
  interface Window {
    claude?: { use(name: string): Promise<unknown> };
  }
}

const KEY = "sti.positions.v1";

function parse(id: string, raw: Record<string, unknown> | undefined): Position | null {
  if (!raw) return null;
  const quantity = Number(raw.quantity);
  const entryPrice = Number(raw.entry_price);
  if (typeof raw.symbol !== "string" || typeof raw.entry_date !== "string") return null;
  if (!(quantity > 0) || !(entryPrice > 0)) return null;
  return { id, symbol: raw.symbol, quantity, entry_price: entryPrice, entry_date: raw.entry_date };
}

function hostedStore(db: HostedDb): PositionStore {
  const collection = db.collection("positions");
  return {
    kind: "hosted",
    subscribe(listener) {
      return collection.onSnapshot(
        (snap) =>
          listener(
            snap.docs.flatMap((doc) => {
              const position = parse(doc.id, doc.data());
              return position ? [position] : [];
            }),
          ),
        () => listener([]),
      );
    },
    save: ({ id, ...body }) => collection.doc(id).set(body),
    remove: (id) => collection.doc(id).delete(),
  };
}

function browserStore(): PositionStore {
  let memory: Position[] = [];
  let kind: StoreKind = "browser";
  const listeners = new Set<(positions: Position[]) => void>();
  const read = (): Position[] => {
    try {
      const stored = JSON.parse(localStorage.getItem(KEY) ?? "[]") as Record<string, unknown>[];
      return stored.flatMap((raw) => {
        const position = parse(String(raw.id), raw);
        return position ? [position] : [];
      });
    } catch {
      kind = "memory";
      return memory;
    }
  };
  const write = (positions: Position[]) => {
    memory = positions;
    try {
      localStorage.setItem(KEY, JSON.stringify(positions));
    } catch {
      kind = "memory";
    }
    listeners.forEach((listener) => listener(positions));
  };
  return {
    get kind() {
      return kind;
    },
    subscribe(listener) {
      listeners.add(listener);
      listener(read());
      return () => listeners.delete(listener);
    },
    save: async (position) =>
      write([...read().filter((p) => p.id !== position.id), position]),
    remove: async (id) => write(read().filter((p) => p.id !== id)),
  };
}

let pending: Promise<PositionStore> | null = null;

/** Resolves once per page load: the hosted database when the page has one, else the browser. */
export function positionStore(): Promise<PositionStore> {
  pending ??= (async () => {
    try {
      const db = (await window.claude?.use("db")) as HostedDb | null | undefined;
      if (db) return hostedStore(db);
    } catch {
      // fall through to the browser store
    }
    return browserStore();
  })();
  return pending;
}

export function newId(): string {
  return `p${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}
