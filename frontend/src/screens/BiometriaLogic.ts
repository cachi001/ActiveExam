/**
 * BiometriaLogic.ts — Lógica pura de Biometria.tsx (C-67 Grupo 6).
 *
 * Módulo extraído para que los tests de vitest puedan verificar el comportamiento
 * sin necesitar @testing-library/react. Patrón: Login.test.ts / CaptureOval.test.tsx.
 *
 * Reglas duras que aplican:
 *   - Regla dominio #5: NUNCA sanción automática (L2.5). El copy refleja decisión humana.
 *   - Regla dominio #7: embedding = dato sensible. NUNCA se muestra ni se loguea.
 *   - Regla código #7: PascalCase en componentes React (este archivo es lógica pura, TS).
 */

// ---------------------------------------------------------------------------
// 6.1 — Gate de navegación: el flujo NUNCA avanza automáticamente.
// Reemplaza el `setTimeout(() => navigate('/sala-espera'), 1400)` que existía.
// El alumno SIEMPRE debe presionar "Continuar" para avanzar, tanto en match
// como en cualquier otro estado. Devuelve `true` siempre: la navegación es
// siempre explícita (gate activo = requiere click).
// ---------------------------------------------------------------------------
export function requiresExplicitContinue(_verified: boolean): boolean {
  // El gate es incondicional: independientemente del resultado,
  // el alumno decide cuándo continuar (L2.5 — transparencia).
  return true;
}

// ---------------------------------------------------------------------------
// 6.4 / 6.2 — Copy principal de la pantalla "verificando"
// Sin jerga: sin "embedding", "coseno", "umbral", "descriptor", "1:1", "distancia".
// ---------------------------------------------------------------------------
export const COPY_VERIFICANDO_PRINCIPAL =
  'Comparando tu imagen con la foto de referencia guardada en el sistema…';

// ---------------------------------------------------------------------------
// 6.4 / 6.2 — Copy principal de la pantalla "verificado" (match exitoso)
// En lenguaje claro. Sin jerga. El detalle técnico (distancia/umbral) va SOLO
// en el bloque <details> colapsado del componente, nunca en este copy.
// ---------------------------------------------------------------------------
export const COPY_VERIFICADO_PRINCIPAL =
  'Listo, confirmamos que sos vos. Ya podés entrar a tu examen.';

// ---------------------------------------------------------------------------
// 6.4 / 6.3 — Copy principal de la pantalla "reintento" (no match)
// Sin jerga. Sin "distancia", "umbral", etc. Los valores numéricos van
// SOLO en el bloque <details> colapsado.
// ---------------------------------------------------------------------------
export const COPY_REINTENTO_PRINCIPAL =
  'No pudimos confirmar que seas vos en esta toma.';

// ---------------------------------------------------------------------------
// 6.6 — Garantía L2.5: ninguna decisión la toma una máquina.
// Siempre presente en las pantallas de resultado (verificado y reintento).
// ---------------------------------------------------------------------------
export const COPY_L25_GUARANTEE =
  'Ninguna decisión la toma una máquina de forma automática; siempre la revisa una persona del equipo.';

// ---------------------------------------------------------------------------
// 6.3 — Mensaje de intentos restantes en lenguaje claro.
// Preserva la lógica de MAX_REINTENTOS sin mostrar jerga.
// ---------------------------------------------------------------------------
export function intentosRestantesMsg(restantes: number): string {
  if (restantes <= 0) {
    return 'No quedan más intentos disponibles. Podés contactar al equipo de soporte.';
  }
  if (restantes === 1) {
    return 'Te queda 1 intento.';
  }
  return `Te quedan ${restantes} intentos.`;
}
