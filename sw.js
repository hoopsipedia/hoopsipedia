// Hoopsipedia Service Worker — PWA offline support
const CACHE_NAME = 'hoopsipedia-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png'
];

// Install: cache critical static assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: network-first for data files, cache-first for static assets
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Skip non-GET requests (POST to /api/chat, etc.)
  if (event.request.method !== 'GET') return;

  // Skip external requests (fonts, analytics, ads, ESPN CDN)
  if (url.origin !== self.location.origin) return;

  // Data files (JSON): network-first with cache fallback
  if (url.pathname.endsWith('.json') && url.pathname !== '/manifest.json') {
    event.respondWith(
      fetch(event.request)
        .then(resp => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return resp;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Static assets: cache-first with network fallback
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(resp => {
        // Cache successful responses for static assets
        if (resp.ok && (url.pathname === '/' || url.pathname.endsWith('.html') || url.pathname.startsWith('/icons/'))) {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return resp;
      });
    })
  );
});
