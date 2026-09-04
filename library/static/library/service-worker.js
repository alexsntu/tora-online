const CACHE_NAME = "tora-online-v2";
const APP_SHELL = [
    "/static/library/style.css",
    "/static/library/manifest.json",
    "/static/library/icons/icon-192.png",
    "/static/library/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") return;

    const url = new URL(request.url);
    const cacheableDestination = ["document", "style", "script", "font", "image"].includes(request.destination);
    const cacheableNavigation = request.mode === "navigate" && !url.search;

    // Never persist admin pages, write endpoints, API-like responses or third-party assets.
    if (url.origin !== self.location.origin || url.pathname.startsWith("/heaven/") ||
        url.pathname === "/track/" || url.pathname.endsWith(".json") ||
        (!cacheableDestination && !cacheableNavigation)) {
        return;
    }

    // Всё, включая статику: сначала сеть (чтобы правки дизайна/текста были видны сразу),
    // при отсутствии сети - последняя закэшированная версия
    event.respondWith(
        fetch(request)
            .then((response) => {
                if (response.ok && response.type === "basic") {
                    const copy = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
                }
                return response;
            })
            .catch(() => caches.match(request))
    );
});
