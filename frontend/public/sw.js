/*
 * Service Worker — cache persistente de los modelos de IA pesados (C-67 fix).
 *
 * Estrategia: CACHE-FIRST, pero ACOTADO únicamente a los assets de modelos de
 * visión (MediaPipe WASM + .task, y modelos de face-api). Todo lo demás —código
 * de la app, /api, HMR de Vite, navegación— NO se intercepta: pasa de largo al
 * navegador como si el SW no existiera, para no servir jamás una versión vieja.
 *
 * Resultado: los ~22 MB de modelos se bajan UNA sola vez y de ahí en más salen
 * de Cache Storage (persistente entre recargas y sesiones). Esto elimina el
 * cuelgue / crash de la pestaña en el teléfono al iniciar la captura biométrica.
 *
 * Mantener MODEL_ASSET_PREFIXES en sync con src/lib/modelPersistence.ts.
 */

const CACHE_NAME = "ae-model-cache-v1";
const MODEL_ASSET_PREFIXES = ["/mediapipe/", "/models/"];

function isModelAssetPath(pathname) {
  return MODEL_ASSET_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

// Activación inmediata: tomar control sin esperar a que se cierren las pestañas.
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // Limpiar versiones viejas del cache de modelos.
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((k) => k.startsWith("ae-model-cache-") && k !== CACHE_NAME)
          .map((k) => caches.delete(k)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;

  // Solo GET de assets de modelos. Cualquier otra cosa: no interceptar.
  if (req.method !== "GET") return;

  let pathname;
  try {
    pathname = new URL(req.url).pathname;
  } catch {
    return;
  }
  if (!isModelAssetPath(pathname)) return;

  // Cache-first: si está cacheado, servir; si no, bajar y guardar.
  event.respondWith(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(req);
      if (cached) return cached;

      const res = await fetch(req);
      // Guardar solo respuestas OK (no cachear 404/errores).
      if (res && res.ok) {
        cache.put(req, res.clone());
      }
      return res;
    })(),
  );
});
