"use client";
// Thin fetch client: JWT auth, timeouts for flaky 2G/3G, last-good-response cache for offline,
// and an outbox that queues writes (e.g. posting a lot) while offline and replays them later.

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "") + "/api/v1";

export type User = {
  id: number; phone: string; name: string; role: "farmer" | "buyer" | "admin"; language: "en" | "hi" | "kn";
  farmer?: { id: number; lat: number; lon: number; village: string; crop_ids: number[] };
  buyer?: { id: number; business_name: string; lat: number; lon: number };
};

const TOKEN = "ar_token";
const USER = "ar_user";
const OUTBOX = "ar_outbox";

const ls = {
  get(k: string) {
    try { return localStorage.getItem(k); } catch { return null; }
  },
  set(k: string, v: string) {
    try { localStorage.setItem(k, v); } catch {}
  },
  del(k: string) {
    try { localStorage.removeItem(k); } catch {}
  },
};

export const session = {
  token: () => ls.get(TOKEN),
  user: (): User | null => {
    const u = ls.get(USER);
    return u ? (JSON.parse(u) as User) : null;
  },
  save(token: string, user: User) {
    ls.set(TOKEN, token);
    ls.set(USER, JSON.stringify(user));
  },
  setUser(user: User) {
    ls.set(USER, JSON.stringify(user));
  },
  clear() {
    ls.del(TOKEN);
    ls.del(USER);
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

export class OfflineError extends Error {}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; timeoutMs?: number } = {}): Promise<T> {
  const method = opts.method || "GET";
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 20000);
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const tok = session.token();
  if (tok) headers.Authorization = `Bearer ${tok}`;
  const cacheKey = `ar_cache:${path}`;
  try {
    const res = await fetch(API_BASE + path, {
      method, headers, signal: ctrl.signal,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    if (!res.ok) {
      if (res.status === 401 && tok) {
        session.clear();
        if (typeof window !== "undefined" && !location.pathname.startsWith("/login")) location.href = "/login/";
      }
      const msg = (data && (data.detail || data.error)) || res.statusText;
      throw new ApiError(res.status, typeof msg === "string" ? msg : JSON.stringify(msg), data);
    }
    if (method === "GET") ls.set(cacheKey, JSON.stringify(data));
    return data as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    // Network failure / timeout: fall back to the last good GET response.
    if (method === "GET") {
      const cached = ls.get(cacheKey);
      if (cached) return JSON.parse(cached) as T;
    }
    throw new OfflineError("offline");
  } finally {
    clearTimeout(timer);
  }
}

// ---- offline outbox ----
type Pending = { path: string; method: string; body: unknown; at: number };

export const outbox = {
  list(): Pending[] {
    try { return JSON.parse(ls.get(OUTBOX) || "[]"); } catch { return []; }
  },
  push(p: Omit<Pending, "at">) {
    const all = outbox.list();
    all.push({ ...p, at: Date.now() });
    ls.set(OUTBOX, JSON.stringify(all));
  },
  async flush(): Promise<number> {
    const all = outbox.list();
    if (!all.length) return 0;
    const left: Pending[] = [];
    let sent = 0;
    for (const p of all) {
      try {
        await api(p.path, { method: p.method, body: p.body });
        sent++;
      } catch (e) {
        if (e instanceof OfflineError) left.push(p); // still offline: keep; server rejections are dropped
      }
    }
    ls.set(OUTBOX, JSON.stringify(left));
    return sent;
  },
};

/** POST that queues itself when offline. Returns {queued:true} in that case. */
export async function postOrQueue<T = any>(path: string, body: unknown): Promise<T | { queued: true }> {
  try {
    return await api<T>(path, { method: "POST", body });
  } catch (e) {
    if (e instanceof OfflineError) {
      outbox.push({ path, method: "POST", body });
      return { queued: true };
    }
    throw e;
  }
}
