const CACHE_NAME = "central-hub-shell-v1";

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    const home = await fetch("/", { cache: "reload" });
    if (!home.ok) throw new Error("Could not cache the app shell.");
    await cache.put("/", home.clone());
    const assets = findShellAssets(await home.text());
    await cacheShellAssets(cache, assets);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith("central-hub-") && key !== CACHE_NAME).map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).then((response) => {
      if (response.ok && url.pathname === "/") {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put("/", copy));
      }
      return response;
    }).catch(async () => (await caches.match("/")) || Response.error()));
    return;
  }

  if (request.destination === "script" || request.destination === "style" || request.destination === "font" || request.destination === "image" || url.pathname.includes("/assets/")) {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok) caches.open(CACHE_NAME).then((cache) => cache.put(request, response.clone()));
      return response;
    })));
  }
});

function findShellAssets(html) {
  const assets = [];
  for (const tag of html.matchAll(/<(?:script|link)\b[^>]*>/gi)) {
    const markup = tag[0];
    const source = markup.match(/\bsrc=["']([^"']+)["']/i)?.[1];
    const href = markup.match(/\bhref=["']([^"']+)["']/i)?.[1];
    const isScript = /^<script\b/i.test(markup);
    const isStyle = /\brel=["'][^"']*(?:stylesheet|modulepreload)[^"']*["']/i.test(markup);
    const asset = isScript ? source : isStyle ? href : undefined;
    if (asset) assets.push(new URL(asset, self.location.origin).href);
  }
  return assets;
}

async function cacheShellAssets(cache, initialAssets) {
  const pending = [...initialAssets];
  const cached = new Set();
  while (pending.length && cached.size < 100) {
    const asset = pending.shift();
    if (!asset || cached.has(asset)) continue;
    cached.add(asset);
    const url = new URL(asset);
    if (url.origin !== self.location.origin) continue;
    try {
      const response = await fetch(url.href, { cache: "reload" });
      if (!response.ok || response.type === "opaque") continue;
      await cache.put(url.href, response.clone());
      const type = response.headers.get("content-type") || "";
      const body = await response.text();
      const references = type.includes("javascript")
        ? [...body.matchAll(/\b(?:from\s*|import\s*)["']([^"']+)["']/g), ...body.matchAll(/\bimport\(\s*["']([^"']+)["']\s*\)/g)].map((match) => match[1])
        : type.includes("css")
          ? [...body.matchAll(/@import\s+(?:url\()?\s*["']?([^"')\s;]+)["']?\s*\)?/gi)].map((match) => match[1])
          : [];
      for (const reference of references) {
        if (!reference.startsWith("data:") && !reference.startsWith("#")) pending.push(new URL(reference, url).href);
      }
    } catch {
      // A missed optional asset does not prevent the cached page from opening.
    }
  }
}
