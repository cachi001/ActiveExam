// Helpers de la página de Auditoría. Puros y testeables.
//
// El propósito de una acción de configuración llega como un JSON
// {"before": {...}, "after": {...}}. En vez de volcarlo crudo, lo diffeamos a
// una lista legible de parámetros que cambiaron (label + antes → después).

export interface ConfigChange {
  key: string;
  label: string;
  antes: string;
  despues: string;
}

/** Etiquetas legibles de los parámetros de configuración conocidos. */
const LABEL_CONFIG: Record<string, string> = {
  chat_habilitado: 'Chat tutor–alumno',
  pausas_habilitadas: 'Pausas del alumno',
  pausa_max_min: 'Duración máx. de pausa (min)',
  umbral_cola_revision: 'Umbral de revisión',
  detectores_activos: 'Detectores activos',
  retencion_dias_default: 'Retención por defecto (días)',
  consent_version_vigente: 'Versión de consentimiento',
  face_absent_ms: 'Rostro ausente (ms)',
  multiple_faces_frames: 'Múltiples rostros (frames)',
  gaze_deviation_threshold: 'Umbral de mirada desviada',
  gaze_sustained_ms: 'Mirada desviada sostenida (ms)',
  gaze_fixation_tolerance: 'Tolerancia de fijación',
};

export function labelConfig(key: string): string {
  return LABEL_CONFIG[key] ?? key.replace(/_/g, ' ');
}

/** Formatea un valor de config para mostrarlo: bool → Sí/No, array → "N ítems". */
function fmtValor(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'boolean') return v ? 'Sí' : 'No';
  if (Array.isArray(v)) return `${v.length} ${v.length === 1 ? 'ítem' : 'ítems'}`;
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

/**
 * Diffea el propósito de una acción de config. Devuelve la lista de parámetros que
 * cambiaron, o `null` si el propósito no tiene forma {before, after} (entonces la
 * card debe mostrar el texto plano tal cual).
 */
export function configDiff(proposito: string | null | undefined): ConfigChange[] | null {
  if (!proposito) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(proposito);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== 'object') return null;
  const obj = parsed as Record<string, unknown>;
  if (!('before' in obj) || !('after' in obj)) return null;

  const before = (obj.before ?? {}) as Record<string, unknown>;
  const after = (obj.after ?? {}) as Record<string, unknown>;
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);

  const cambios: ConfigChange[] = [];
  for (const key of keys) {
    if (key === 'version') continue; // metadato, no es un parámetro configurable
    const a = before[key];
    const b = after[key];
    if (JSON.stringify(a) !== JSON.stringify(b)) {
      cambios.push({ key, label: labelConfig(key), antes: fmtValor(a), despues: fmtValor(b) });
    }
  }
  return cambios;
}
