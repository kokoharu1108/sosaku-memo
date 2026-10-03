// 創作メモ帳 — オフライン起動用 Service Worker
// アプリを更新したら CACHE の番号を上げると、次回起動時に新しい版へ切り替わります。
const CACHE = "sosaku-memo-v14";
// フォントは版をまたいで使い回す（更新のたびに消すと、オフラインで文字の形が変わってしまうため）
const FONTS = "sosaku-memo-fonts";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icons/icon-192.png", "./icons/icon-512.png", "./icons/apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  // ブラウザの一時保存（HTTPキャッシュ）に残った古い版を拾わないよう、必ずサーバーから取り直す
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL.map((u) => new Request(u, { cache: "reload" })))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE && k !== FONTS && k.startsWith("sosaku-memo")).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // アプリ本体（同じサイト内）: 保存済みをすぐ表示し、裏で最新版を取得
  if (url.origin === self.location.origin) {
    e.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const cached = await cache.match(req, { ignoreSearch: true }) || (req.mode === "navigate" ? await cache.match("./index.html") : null);
        const network = fetch(req).then((res) => { if (res.ok) cache.put(req, res.clone()); return res; }).catch(() => null);
        if (cached) { e.waitUntil(network); return cached; }
        return (await network) || new Response("オフラインです", { status: 503, headers: { "content-type": "text/plain; charset=utf-8" } });
      })
    );
    return;
  }

  // Google Fonts: 一度読み込んだフォントを保存してオフラインでも使う
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    e.respondWith(
      caches.open(FONTS).then(async (cache) => {
        const cached = await cache.match(req);
        if (cached) return cached;
        try { const res = await fetch(req); if (res.ok || res.type === "opaque") cache.put(req, res.clone()); return res; }
        catch { return new Response("", { status: 503 }); }
      })
    );
  }
  // AI検索のAPIなどはそのままネットワークへ
});
