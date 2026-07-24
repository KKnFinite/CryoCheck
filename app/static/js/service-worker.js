const CACHE_NAME = "cryocheck-static-shell-v1";
const APP_SHELL_ASSETS = [
  "/static/css/app.css",
  "/static/fonts/neofont/NeoFont.ttf",
  "/static/fonts/neofont/NeoFont.woff2",
  "/static/img/favicon.svg",
  "/static/img/icon-180.png",
  "/static/img/icon-192.png",
  "/static/img/icon-512.png",
  "/static/img/icon-maskable-512.png",
  "/static/js/exception-export.js",
  "/static/js/mobile-shell.js",
  "/static/js/pwa-install.js",
  "/static/js/upload.js",
  "/static/manifest.webmanifest",
];
const APP_SHELL_PATHS = new Set(APP_SHELL_ASSETS);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(
        names
          .filter((name) => name.startsWith("cryocheck-static-shell-"))
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const requestUrl = new URL(event.request.url);
  const isStaticShellRequest = (
    event.request.method === "GET"
    && requestUrl.origin === self.location.origin
    && APP_SHELL_PATHS.has(requestUrl.pathname)
  );
  if (!isStaticShellRequest) {
    return;
  }

  event.respondWith((async () => {
    const cachedResponse = await caches.match(event.request);
    if (cachedResponse) {
      return cachedResponse;
    }
    const networkResponse = await fetch(event.request);
    if (networkResponse.ok && networkResponse.type === "basic") {
      const cache = await caches.open(CACHE_NAME);
      await cache.put(event.request, networkResponse.clone());
    }
    return networkResponse;
  })());
});
