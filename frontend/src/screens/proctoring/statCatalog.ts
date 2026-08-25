/**
 * statCatalog — fuente ÚNICA de vocabulario de las StatCards (C-72 sección 11).
 *
 * El PROBLEMA que cierra: la misma métrica aparecía con label/icono/tono distintos
 * según la pantalla ("Eventos" vs "Eventos totales" vs "Incidencias"; `notifications`
 * vs `warning`; `info` vs `warning`; Sesiones con `video_library` —engañoso, no hay
 * grabación—). Eso confunde a quien revisa. Acá se define UNA vez por métrica.
 *
 * La descripción (`sub`) puede contextualizarse por pantalla vía override (el scope
 * legítimamente cambia: "en el lote actual" en vivo vs "en la sesión" en el detalle),
 * pero el label / icono / tono son canónicos y NO se tocan pantalla por pantalla.
 */
import type { ReactNode } from 'react';
import type { StatTono } from './StatCard';

export type StatMetricKey =
  | 'eventos'
  | 'discrepancias'
  | 'riesgoAlto'
  | 'sesiones'
  | 'sesionesActivas'
  | 'enColaRevision'
  | 'examenes';

export interface StatMeta {
  icon: string;
  label: string;
  tono: StatTono;
  /** Descripción por defecto; una pantalla puede pasar un scope propio. */
  defaultSub: string;
}

export const STAT_META: Record<StatMetricKey, StatMeta> = {
  // Eventos discretos de proctoring. Canónico: "Eventos" (nunca "Incidencias").
  eventos: { icon: 'notifications', label: 'Eventos', tono: 'info', defaultSub: 'detectados' },
  // Re-inferencia server-side que no coincidió con el cliente (cadena de custodia).
  discrepancias: { icon: 'rule', label: 'Discrepancias', tono: 'warning', defaultSub: 'verificadas en server' },
  // Sesiones cuyo score supera el umbral de priorización (L2.5: prioriza, no sanciona).
  riesgoAlto: { icon: 'priority_high', label: 'Riesgo alto', tono: 'error', defaultSub: 'superan el umbral' },
  // Total de sesiones registradas. `groups`, NO `video_library` (no hay video, RN-CC).
  // Tono `success`: no choca con `Exámenes`/`Sesiones activas` (primary) en las
  // filas donde conviven.
  sesiones: { icon: 'groups', label: 'Sesiones', tono: 'success', defaultSub: 'registradas' },
  // Sesiones rindiendo en este momento (vista en vivo).
  sesionesActivas: { icon: 'sensors', label: 'Sesiones activas', tono: 'primary', defaultSub: 'rindiendo ahora' },
  // Sesiones con score >= umbral de la Cola de revision (C-76 tarea 20). Distinto
  // de `riesgoAlto` en el LABEL (comunica el "por que importa": entran a cola de
  // revision humana) aunque comparten el mismo umbral vivo server-side.
  enColaRevision: { icon: 'gavel', label: 'Sobre el umbral de riesgo', tono: 'error', defaultSub: 'entran a Cola de revisión' },
  // c-78 D4: inventario VIGENTE del catálogo. La tarjeta del Panel de administración
  // la tenía hardcodeada (icono/label/tono propios) y esquivaba el catálogo. Los
  // exámenes dados de baja no cuentan acá — ver la baja lógica de c-78 D2.
  examenes: { icon: 'assignment', label: 'Exámenes', tono: 'primary', defaultSub: 'en el catálogo' },
};

/** Props canónicas de una StatCard para una métrica. `subOverride` solo cambia la
 * descripción (scope); label/icono/tono quedan fijos por el catálogo. */
export function statProps(
  key: StatMetricKey,
  value: ReactNode,
  subOverride?: ReactNode,
): { icon: string; label: string; tono: StatTono; value: ReactNode; sub: ReactNode } {
  const meta = STAT_META[key];
  return {
    icon: meta.icon,
    label: meta.label,
    tono: meta.tono,
    value,
    sub: subOverride ?? meta.defaultSub,
  };
}
