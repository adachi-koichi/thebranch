const CACHE_VERSION = 'v1';
const CACHE_NAME = `thebranch-${CACHE_VERSION}`;

const ASSETS_TO_CACHE = [
  '/',
  '/dashboard/',
  '/dashboard/index.html',
  '/dashboard/manifest.json',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js',
  'https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js',
  'https://unpkg.com/vis-network/standalone/umd/vis-network.min.js'
];

// Install event - cache assets
self.addEventListener('install', event => {
  console.log('[SW] Installing service worker...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[SW] Caching assets...');
        return cache.addAll(ASSETS_TO_CACHE).catch(err => {
          console.warn('[SW] Some assets failed to cache:', err);
          return Promise.resolve();
        });
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip requests to external APIs
  if (url.origin !== self.location.origin && !request.url.includes('cdn.jsdelivr.net') && !request.url.includes('unpkg.com')) {
    return;
  }

  event.respondWith(
    caches.match(request)
      .then(response => {
        if (response) {
          console.log('[SW] Serving from cache:', request.url);
          return response;
        }

        return fetch(request)
          .then(response => {
            // Don't cache non-successful responses
            if (!response || response.status !== 200 || response.type === 'error') {
              return response;
            }

            // Clone the response before caching
            const responseToCache = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(request, responseToCache);
            });

            return response;
          })
          .catch(() => {
            console.log('[SW] Network request failed, serving offline fallback for:', request.url);
            // Return a basic offline page or cached response
            return caches.match(request) || caches.match('/dashboard/index.html');
          });
      })
  );
});

// Handle messages from clients
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
