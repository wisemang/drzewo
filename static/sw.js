const CACHE_NAME = "treeseek-v4";
const APP_SHELL = [
    "/",
    "/offline",
    "/manifest.webmanifest",
    "/static/css/styles.css",
    "/static/css/L.Icon.Pulse.css",
    "/static/js/script.js",
    "/static/js/L.Icon.Pulse.js",
    "/static/js/leaflet.rotatedMarker.js",
    "/static/images/favicon.png",
    "/static/images/tree-gross-outline-svgrepo-com.svg",
    "/static/images/apple-touch-icon-180-v2.png",
    "/static/images/icon-192-v2.png",
    "/static/images/icon-512-v2.png"
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((names) =>
            Promise.all(
                names
                    .filter((name) => name !== CACHE_NAME)
                    .map((name) => caches.delete(name))
            )
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") {
        return;
    }

    const request = event.request;
    const url = new URL(request.url);

    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    const copy = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
                    return response;
                })
                .catch(async () => {
                    const cached = await caches.match(request);
                    if (cached) {
                        return cached;
                    }
                    return caches.match("/offline");
                })
        );
        return;
    }

    if (url.origin === self.location.origin) {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    const copy = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
                    return response;
                })
                .catch(async () => {
                    const cached = await caches.match(request);
                    if (cached) {
                        return cached;
                    }
                    if (request.destination === "document") {
                        return caches.match("/offline");
                    }
                    throw new Error("Network unavailable and no cached asset found.");
                })
        );
    }
});
