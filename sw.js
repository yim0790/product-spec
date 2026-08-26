// 상품스펙 조회 서비스워커 — 화면(HTML)은 네트워크 우선, 아이콘·매니페스트는 캐시 우선
// 스펙 데이터가 index.html 안에 통째로 들어 있으므로, HTML만 네트워크 우선으로 두면 항상 최신이 된다.
const VERSION = 1;
const CACHE = 'specviewer-v' + VERSION;
const STATIC = [
  './', './index.html', './manifest.json',
  './icons/icon-192.png', './icons/icon-384.png',
  './icons/icon-512.png', './icons/icon-512-maskable.png'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  const isHTML = e.request.mode === 'navigate' || url.pathname.endsWith('/index.html');
  if (isHTML) {
    e.respondWith(
      fetch(e.request).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put('./index.html', copy));
        return res;
      }).catch(() => caches.match('./index.html'))
    );
    return;
  }
  e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request)));
});
