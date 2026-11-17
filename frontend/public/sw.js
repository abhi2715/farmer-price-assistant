/* AgriRoute service worker — offline-first shell, cached data, tiny and dependency-free.
 *  - App pages (HTML): network-first, fall back to cache (works offline after first visit)
 *  - Next static assets (/_next/static, icons): cache-first (content-hashed, immutable)
 *  - API GETs: network-first with cached fallback, so last-seen prices/forecasts show offline
 *  - API writes are never cached; the app queues them in an outbox while offline
 */
const VERSION = "ar-v1";
const SHELL = ["/", "/login/", "/farmer/", "/farmer/forecast/", "/farmer/lots/", "/farmer/alerts/", "/buyer/", "/admin/",
  "/manifest.webmanifest", "/icons/icon.svg", "/icons/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

const putCache = (name, req, res) => caches.open(name).then((c) => c.put(req, res));

async function networkFirst(req, cacheName) {
  try {
    const res = await fetch(req);
    if (res.ok) putCache(cacheName, req, res.clone());
    return res;
  } catch (err) {
    const hit = await caches.match(req, { ignoreSearch: false });
    if (hit) return hit;
    if (req.mode === "navigate") return (await caches.match("/farmer/")) || Response.error();
    throw err;
  }
}

async function cacheFirst(req) {
  const hit = await caches.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) putCache(VERSION + "-static", req, res.clone());
  return res;
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.startsWith("/api/")) {
    if (req.headers.get("Authorization") || url.pathname.match(/\/(crops|mandis|forecasts|prices)/)) {
      e.respondWith(networkFirst(req, VERSION + "-api"));
    }
    return;
  }
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/")) {
    e.respondWith(cacheFirst(req));
  } else if (req.mode === "navigate" || req.destination === "document") {
    e.respondWith(networkFirst(req, VERSION));
  }
});
