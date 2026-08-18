/**
 * Helpers de presentación compartidos por las pantallas de proctoring (lista + detalle).
 *
 * Centraliza el formateo de fechas y la lógica de color por riesgo/score/veredicto,
 * para que los sub-componentes no dupliquen reglas y queden por debajo del límite
 * de líneas. NADA de hardcodear umbrales en cada tarjeta: la fuente es este archivo.
 */
import type { VeredictoReinferencia } from '../../lib/types';

/**
 * Umbral "alto" sembrable desde la config efectiva.
 *
 * Patrón análogo a `seedScoringWeights` de scoringWeights.ts:
 *  - `seedUmbralAlto(v)` — llamado desde `effectiveConfigCache.loadEffectiveConfig()`
 *    para propagar `umbral_cola_revision` sin un segundo round-trip.
 *  - `getUmbralAlto()`   — O(1), sin red; usado en `nivelRiesgo()` y en las vistas.
 *  - Default 70 (igual que el mock del backend en api.ts).
 *
 * @deprecated SCORE_UMBRAL_ALTO — se mantiene solo para compatibilidad con
 * importaciones existentes. Usar `getUmbralAlto()` en código nuevo.
 */
let _umbralAlto = 70;

/** Siembra el umbral de riesgo alto desde la config efectiva (sin red). Idempotente. */
export function seedUmbralAlto(v: number): void {
  _umbralAlto = v;
}

/** Devuelve el umbral de riesgo alto vigente (default 70, o el sembrado por la config). */
export function getUmbralAlto(): number {
  return _umbralAlto;
}

/** Resetea el umbral al default (70). Solo para tests. */
export function resetUmbralAlto(): void {
  _umbralAlto = 70;
}

/**
 * Constante de compatibilidad. ATENCIÓN: su valor es el default inicial (70) y NO
 * se actualiza cuando se siembra la config. Usar `getUmbralAlto()` para el valor vivo.
 * @deprecated Usar `getUmbralAlto()`.
 */
export const SCORE_UMBRAL_ALTO = 70;
/** Umbral de score a partir del cual una sesión se considera de riesgo medio. */
export const SCORE_UMBRAL_MEDIO = 30;

/** Fecha absoluta legible (es-AR). */
export function formatFecha(iso: string, conSegundos = false): string {
  try {
    return new Date(iso).toLocaleString('es-AR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      ...(conSegundos ? { second: '2-digit' } : {}),
    });
  } catch {
    return iso;
  }
}

/** Fecha relativa amable ("hace 5 min", "ayer", "hace 3 d"). */
export function formatFechaRelativa(iso: string): string {
  try {
    const ahora = Date.now();
    const t = new Date(iso).getTime();
    const diffSeg = Math.round((ahora - t) / 1000);
    if (diffSeg < 60) return 'recién';
    const diffMin = Math.round(diffSeg / 60);
    if (diffMin < 60) return `hace ${diffMin} min`;
    const diffHoras = Math.round(diffMin / 60);
    if (diffHoras < 24) return `hace ${diffHoras} h`;
    const diffDias = Math.round(diffHoras / 24);
    if (diffDias === 1) return 'ayer';
    if (diffDias < 7) return `hace ${diffDias} d`;
    return formatFecha(iso);
  } catch {
    return iso;
  }
}

/** Nivel de riesgo derivado del score. */
export type NivelRiesgo = 'bajo' | 'medio' | 'alto';

export function nivelRiesgo(score: number): NivelRiesgo {
  if (score >= getUmbralAlto()) return 'alto';
  if (score >= SCORE_UMBRAL_MEDIO) return 'medio';
  return 'bajo';
}

/** Clase de color de texto para el score, según su nivel de riesgo. */
export function scoreTextColor(score: number): string {
  const nivel = nivelRiesgo(score);
  if (nivel === 'alto') return 'text-error';
  if (nivel === 'medio') return 'text-warning';
  return 'text-success';
}

/** Clase de borde-izquierdo (acento) para la tarjeta de sesión, según riesgo. */
export function scoreAccentBorder(score: number): string {
  const nivel = nivelRiesgo(score);
  if (nivel === 'alto') return 'border-l-error';
  if (nivel === 'medio') return 'border-l-warning';
  return 'border-l-success';
}

/**
 * Fondo + borde SUAVE para la tarjeta entera, tintado por nivel de riesgo.
 *
 * Reemplaza el acento "fuerte" (stripe lateral saturado) por el color del badge
 * en su versión clara (los `*-container` del design system). Así una sesión de
 * riesgo medio se ve con toda la card en amarillo clarito, no con una franja
 * amarilla fuerte sobre blanco. Pensado para usarse como `border ${scoreCardSurface(score)}`.
 */
export function scoreCardSurface(score: number): string {
  return `${scoreSoftBg(score)} ${scoreSoftBorder(score)}`;
}

/** C-72: acento de riesgo para las cards del Registro de sesiones. En vez de teñir
 * TODO el fondo (que se veía poco profesional), deja el fondo limpio y pone un borde
 * IZQUIERDO grueso de color por riesgo (rojo alto / ámbar medio / verde bajo). La
 * sombra y el hover los pone la card. */
export function scoreCardAcento(score: number): string {
  const nivel = nivelRiesgo(score);
  const borde =
    nivel === 'alto' ? 'border-l-error'
    : nivel === 'medio' ? 'border-l-warning'
    : 'border-l-success';
  return `bg-surface-container-lowest border-outline-variant/60 border-l-4 ${borde}`;
}

/** Solo el fondo claro tintado por riesgo (para filas/elementos sin borde propio). */
export function scoreSoftBg(score: number): string {
  const nivel = nivelRiesgo(score);
  if (nivel === 'alto') return 'bg-error-container/40';
  if (nivel === 'medio') return 'bg-warning-container/50';
  return 'bg-success-container/25';
}

/** Solo el color del borde acorde al riesgo (combina con `border`). */
export function scoreSoftBorder(score: number): string {
  const nivel = nivelRiesgo(score);
  if (nivel === 'alto') return 'border-error/30';
  if (nivel === 'medio') return 'border-warning/30';
  return 'border-success/20';
}

/**
 * Fondo translúcido para elementos INTERNOS de una card tintada (chips de métrica,
 * chip de score). Blanco semitransparente que se integra con el tinte de la card,
 * en vez de un gris sólido (`surface-container-*`) que se ve sucio sobre el color.
 */
export const INNER_CHIP_BG = 'bg-white/60';

/** Clase de relleno del gauge de score. */
export function gaugeFill(score: number): string {
  const nivel = nivelRiesgo(score);
  if (nivel === 'alto') return 'bg-error';
  if (nivel === 'medio') return 'bg-warning';
  return 'bg-success';
}

/** Tono del Badge para el modo de la sesión. */
export function modoBadgeTone(modo: string): 'primary' | 'neutral' | 'warning' {
  if (modo === 'examen') return 'primary';
  if (modo === 'diagnostico') return 'warning';
  return 'neutral';
}

/** Etiqueta legible del modo de la sesión. */
export function modoLabel(modo: string): string {
  const map: Record<string, string> = {
    diagnostico: 'Diagnóstico',
    examen: 'Examen',
    test: 'Prueba',
  };
  return map[modo] ?? modo;
}

// --- Veredicto de re-inferencia server-side (cliente = sensor no confiable) ---

export function verdictClasses(v: VeredictoReinferencia | null | undefined): string {
  if (v === 'coincide') return 'bg-success-container text-success border-success/30';
  if (v === 'discrepancia') return 'bg-error-container text-on-error-container border-error/30';
  return 'bg-white/70 text-on-surface-variant border-outline-variant/40';
}

export function verdictIcon(v: VeredictoReinferencia | null | undefined): string {
  if (v === 'coincide') return 'check_circle';
  if (v === 'discrepancia') return 'report';
  if (v === 'error') return 'error';
  return 'info';
}

export function verdictLabel(v: VeredictoReinferencia | null | undefined): string {
  const map: Record<string, string> = {
    coincide: 'Coincide con el navegador',
    discrepancia: 'No coincide con el navegador',
    sin_referencia: 'Sin referencia previa',
    error: 'Error al verificar',
    no_evaluado: 'No evaluado',
  };
  return map[v ?? ''] ?? 'No evaluado';
}

/**
 * ¿El veredicto aporta evidencia que valga la pena mostrar?
 * `no_evaluado`/null = el servidor no re-infirió (p. ej. evento sin captura) → no
 * se muestra la fila para no ensuciar con ruido sin valor.
 */
export function tieneVeredicto(v: VeredictoReinferencia | null | undefined): boolean {
  return v === 'coincide' || v === 'discrepancia' || v === 'sin_referencia' || v === 'error';
}

/** snake_case / minúsculas → "Texto legible" (fallback cuando no hay etiqueta). */
export function humanizarLabel(raw: string): string {
  const limpio = (raw ?? '').replace(/_/g, ' ').trim();
  return limpio.charAt(0).toUpperCase() + limpio.slice(1);
}

/** Fondo claro tintado por SEVERIDAD del evento (para la card del evento, sin
 *  bordes grises ni stripe fuerte). Coherente con scoreSoftBg de las sesiones. */
export function severidadSoftBg(sev: string): string {
  // El backend guarda la severidad en masculino (bajo/medio/alto/critico) y el
  // cliente la maneja en femenino (baja/media/alta/critica); aceptamos ambos.
  if (sev === 'critica' || sev === 'critico' || sev === 'alta' || sev === 'alto') return 'bg-error-container/40';
  if (sev === 'media' || sev === 'medio') return 'bg-warning-container/50';
  if (sev === 'baja' || sev === 'bajo') return 'bg-success-container/25';
  return 'bg-surface-container-lowest';
}

// --- Formateo de payload de eventos (legibilidad para revisión humana) ---

/**
 * Tabla de etiquetas legibles para las claves más comunes del payload de un
 * evento. Lo que NO está acá cae al fallback (key con guiones bajos a espacios,
 * capitalizada). Mantener pequeño y honesto: si una clave no aparece, no pasa
 * nada — el fallback es razonable.
 */
const PAYLOAD_KEY_LABELS: Record<string, string> = {
  sostenido_ms: 'Duración',
  duracion_ms: 'Duración',
  tiempo_ms: 'Tiempo',
  ms: 'Duración',
  // C-72 sección 7.6: duración de la ausencia en una reanudación (segundos, medida
  // server-side). El revisor la lee para dimensionar cuánto estuvo fuera el alumno.
  ausencia_seg: 'Duración de ausencia',
  face_count: 'Rostros',
  faces: 'Rostros',
  rostros: 'Rostros',
  trigger_evidence: 'Disparó evidencia',
  // C-76 (15.5): hash del contenido pegado — evidencia REAL (nunca el contenido).
  clipboard_sha256: 'Hash de lo pegado',
  gaze: 'Dirección de mirada',
  gaze_x: 'Mirada X',
  gaze_y: 'Mirada Y',
  yaw: 'Yaw',
  pitch: 'Pitch',
  roll: 'Roll',
  accion: 'Acción',
};

/** Valores de `accion` del evento `copiar_pegar` (stateTransitionRules.ts envía
 * el nombre crudo del evento del navegador: 'copy' | 'paste' | 'cut'). */
const ACCION_LABELS: Record<string, string> = {
  copy: 'Copiar',
  paste: 'Pegar',
  cut: 'Cortar',
};

/**
 * Convierte un vector de mirada {x, y} (normalizado a [-1, 1] aprox., donde
 * x>0 = derecha, y>0 = abajo según convención de visión por computadora) en
 * una etiqueta cardinal humana. Si la magnitud es chica, devuelve "centro".
 *
 * Ejemplos:
 *   { x: -0.22, y: -0.05 } -> "izquierda"
 *   { x:  0.30, y:  0.40 } -> "abajo-derecha"
 *   { x:  0.02, y: -0.01 } -> "centro"
 */
export function formatGazeDirection(gaze: { x?: unknown; y?: unknown }): string {
  const x = typeof gaze.x === 'number' ? gaze.x : 0;
  const y = typeof gaze.y === 'number' ? gaze.y : 0;
  const magnitud = Math.hypot(x, y);
  // Tolerancia: por debajo de ~0.1 la mirada está alineada al frente.
  if (magnitud < 0.1) return 'centro';

  // Solo el eje dominante si el otro es despreciable (< 30% del dominante).
  const ax = Math.abs(x);
  const ay = Math.abs(y);
  const horiz = x < 0 ? 'izquierda' : 'derecha';
  const vert = y < 0 ? 'arriba' : 'abajo';
  if (ay < ax * 0.3) return horiz;
  if (ax < ay * 0.3) return vert;
  return `${vert}-${horiz}`;
}

/** Etiqueta humana para una clave de payload. */
export function formatPayloadKey(key: string): string {
  if (key in PAYLOAD_KEY_LABELS) return PAYLOAD_KEY_LABELS[key];
  // Fallback: snake_case → "Snake case"
  const limpio = key.replace(/_/g, ' ').trim();
  return limpio.charAt(0).toUpperCase() + limpio.slice(1);
}

/**
 * Convierte una duración en milisegundos a una etiqueta legible.
 *   500    → "0,5 s"
 *   3000   → "3 s"
 *   3200   → "3,2 s"
 *   75_000 → "1 min 15 s"
 * Para valores < 1 s pero ≥ 100 ms usamos décimas de segundo; bajo 100 ms
 * mostramos los milisegundos directos (señal cruda, no rotamos a "0,0 s").
 */
export function formatDuracionMs(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return `${ms} ms`;
  if (ms < 100) return `${Math.round(ms)} ms`;
  if (ms < 60_000) {
    const segundos = ms / 1000;
    // 1 decimal solo si aporta info (3,2 s pero no 3,0 s).
    const fmt = Number.isInteger(segundos) || segundos >= 10
      ? segundos.toFixed(0)
      : segundos.toFixed(1).replace('.', ',');
    return `${fmt} s`;
  }
  const totalSeg = Math.round(ms / 1000);
  const min = Math.floor(totalSeg / 60);
  const seg = totalSeg % 60;
  return seg === 0 ? `${min} min` : `${min} min ${seg} s`;
}

/**
 * Formatea el valor de una clave de payload pensando en lectura humana:
 * - claves que terminan en `_ms` o que son exactamente `ms` → "X s" / "X min Y s"
 * - clave `gaze` con shape {x, y} → "izquierda" / "abajo-derecha" / "centro"
 * - booleanos → "Sí"/"No"
 * - números con muchos decimales → 2 decimales
 * - el resto → String(v)
 */
export function formatPayloadValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (key === 'accion' && typeof value === 'string') return ACCION_LABELS[value] ?? value;
  // Hash largo: truncar igual que el sha256 del screenshot (16 chars + …), no
  // volcar los 64 caracteres en un chip.
  if (key === 'clipboard_sha256' && typeof value === 'string') {
    return value.length > 16 ? `${value.slice(0, 16)}…` : value;
  }
  const esMs = key === 'ms' || /_ms$/.test(key);
  if (esMs && typeof value === 'number') return formatDuracionMs(value);
  // Claves en SEGUNDOS (p. ej. `ausencia_seg`): reusar el mismo formateo legible
  // (ms) pasando a ms, para que "75 s" se lea "1 min 15 s" como el resto.
  const esSeg = key === 'seg' || /_seg$/.test(key);
  if (esSeg && typeof value === 'number') return formatDuracionMs(value * 1000);
  if (
    key === 'gaze' &&
    typeof value === 'object' &&
    value !== null &&
    'x' in value &&
    'y' in value
  ) {
    return formatGazeDirection(value as { x: unknown; y: unknown });
  }
  if (typeof value === 'boolean') return value ? 'Sí' : 'No';
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return String(value);
    return value.toFixed(2).replace('.', ',');
  }
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

// --- Join del catálogo académico: enriquece una sesión con su contexto ---

/**
 * Contexto académico de una sesión, derivado del `exam_id` contra el catálogo local.
 * Reutilizable por las tres pantallas de proctoring (cola, grabadas, en vivo).
 */
export interface ExamInfo {
  examNombre: string;
  materiaNombre: string;
  comisionNombre: string;
  docente: string;
}

