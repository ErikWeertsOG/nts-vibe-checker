// NTS Vibe Checker — temporary kill switch.
// Old SW versions trapped users on stale builds; this unregisters
// itself, clears all caches, and force-refreshes any open clients.
// Re-introduce a proper SW once the site is verified stable on mobile.

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", async (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
      await self.registration.unregister();
      const clients = await self.clients.matchAll({ type: "window" });
      for (const c of clients) c.navigate(c.url);
    })()
  );
});
