/** PanelCraft AI Service Worker for offline shell caching & Android/Desktop PWA installability */
const CACHE_NAME = "panelcraft-ai-v0.6.0";
const SHELL_ASSETS = [
  "/",
  "/styles/app.css",
  "/js/app.js",
  "/js/api.js",
  "/js/i18n.js",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET" || event.request.url.includes("/api/")) {
    return;
  }
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
