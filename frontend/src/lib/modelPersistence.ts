/**
 * modelPersistence — persistencia de los modelos de IA pesados en el navegador
 * (C-67 fix: "descargá los modelos una vez y no los vuelvas a bajar nunca más").
 *
 * PROBLEMA: la captura de referencia biométrica baja ~22 MB de modelos cada vez
 * (WASM de MediaPipe + .task + modelos de face-api). En el teléfono, sobre el
 * túnel, eso cuelga la pantalla y puede crashear la pestaña (vuelve al perfil).
 *
 * SOLUCIÓN: un Service Worker (public/sw.js) cachea esos assets con estrategia
 * cache-first. Se bajan UNA vez y de ahí en más se sirven desde Cache Storage
 * (persistente entre recargas y sesiones). El SW está ACOTADO solo a los assets
 * de modelos — todo lo demás (código de la app, /api, HMR) pasa de largo y nunca
 * se cachea, para no servir jamás una versión vieja.
 *
 * SOBERANÍA DE DATOS (RD-7): los modelos ya se sirven self-hosted desde el mismo
 * origen (/mediapipe, /models). El cache solo evita re-descargarlos; nunca toca
 * un CDN externo.
 */

/**
 * Prefijos de ruta (como segmentos) cuyos GET deben cachearse de forma persistente.
 * Mantener en sync con la lista equivalente dentro de public/sw.js.
 */
export const MODEL_ASSET_PREFIXES = ["/mediapipe/", "/models/"] as const;

/**
 * ¿Esta URL apunta a un asset de modelo que debe persistirse?
 *
 * Acepta tanto un pathname (`/mediapipe/x.task`) como una URL absoluta
 * (`https://host/mediapipe/x.task`): en ese caso se evalúa solo el pathname.
 * El prefijo debe estar al INICIO del pathname (segmento de ruta), para no
 * confundir `/api/models-list` con un asset de `/models/`.
 */
export function isModelAssetPath(urlOrPath: string): boolean {
  let pathname = urlOrPath;
  // Si es una URL absoluta, quedarnos con el pathname.
  if (/^https?:\/\//i.test(urlOrPath)) {
    try {
      pathname = new URL(urlOrPath).pathname;
    } catch {
      return false;
    }
  }
  return MODEL_ASSET_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

/**
 * Registra el Service Worker de cache de modelos (public/sw.js).
 *
 * Idempotente y defensivo: si el navegador no soporta Service Workers o el
 * registro falla, NO lanza — la app sigue funcionando (los modelos se bajarán
 * sin cache, como antes). Llamar una vez al arrancar la app (main.tsx).
 */
export function registerModelCacheWorker(): void {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
    return;
  }
  // C-67: en DESARROLLO NO registrar el SW y, además, DESREGISTRAR cualquiera ya
  // instalado + limpiar sus caches. El SW (cache de modelos) en dev hacía que el
  // teléfono quedara "pegado" a una versión vieja de la app y no se actualizara nunca
  // por más que se refrescara. En PROD sí se registra (cada release es inmutable).
  if (import.meta.env.DEV) {
    navigator.serviceWorker
      .getRegistrations?.()
      .then((regs) => regs.forEach((r) => r.unregister()))
      .catch(() => {});
    if (typeof caches !== "undefined") {
      caches.keys?.().then((keys) => keys.forEach((k) => caches.delete(k))).catch(() => {});
    }
    return;
  }
  // Registrar tras 'load' para no competir con la carga inicial de la app.
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Falla silenciosa: sin SW la app funciona igual (sin cache persistente).
    });
  });
}
