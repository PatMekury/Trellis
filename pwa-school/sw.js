// Trellis school advisory — service worker
// Offline strategy: cache-first for static assets and forecast data.

const CACHE = "trellis-school-v1";
const FILES = [
  "./",
  "./index.html",
  "./manifest.json",
  "./forecast.json",
  "./ward_timeseries.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  // For navigation requests fall through to network with cache fallback
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match("./index.html"))
    );
    return;
  }
  // Cache-first for everything else
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((resp) => {
        // Cache successful responses
        if (resp && resp.status === 200 && req.method === "GET") {
          const respClone = resp.clone();
          caches.open(CACHE).then((cache) => cache.put(req, respClone));
        }
        return resp;
      }).catch(() => {
        // Network and cache both failed — return a minimal offline response for JSON
        if (req.url.endsWith(".json")) {
          return new Response("[]", { headers: { "Content-Type": "application/json" } });
        }
        return new Response("offline", { status: 503 });
      });
    })
  );
});
