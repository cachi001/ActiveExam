// Mapas de presentación de eventos/severidad (extraídos de api.ts — refactor c-76).
// Puros: solo dependen de los tipos del dominio, sin estado ni red.
import type { Severidad, TipoEvento } from './types';

/** Descripción larga de cada tipo de evento (para tooltips / detalle). */
export const DESC_EVENTO: Record<TipoEvento, string> = {
  rostro_ausente: 'No se detectó rostro en el encuadre por más de 3 segundos.',
  multiples_rostros: 'Se detectaron múltiples rostros simultáneos en cámara.',
  mirada_desviada_sostenida: 'Patrón de mirada sostenido hacia un punto fijo fuera de pantalla.',
  perdida_de_foco: 'El estudiante minimizó la ventana o la ventana perdió el foco del sistema operativo.',
  cambio_pestana: 'El estudiante cambió o abrió otra pestaña del navegador durante el examen.',
  monitor_adicional: 'Se detectó un segundo monitor conectado al equipo.',
  salida_pantalla_completa: 'El estudiante salió del modo de pantalla completa durante el examen.',
  copiar_pegar: 'Se detectó una acción de copiar o pegar durante el examen (sin capturar contenido).',
  corte_conectividad_prolongado: 'Corte de conectividad prolongado (> 5 min) con el canal de eventos.',
  recarga_pagina: 'El estudiante recargó la página y volvió enseguida (reapertura benigna).',
  reanudacion_tardia: 'El estudiante reanudó la rendición tras una ausencia prolongada.',
};

export function descripcionEvento(t: TipoEvento): string {
  return DESC_EVENTO[t];
}

/** Etiqueta corta de severidad. */
export const SEVERIDAD_LABEL: Record<Severidad, string> = {
  baseline: 'Base', baja: 'Baja', media: 'Media', alta: 'Alta', critica: 'Crítica',
};

/** Etiqueta corta de cada tipo de evento (para chips / tablas). */
export const TIPO_EVENTO_LABEL: Record<TipoEvento, string> = {
  rostro_ausente: 'Rostro ausente',
  multiples_rostros: 'Múltiples rostros',
  mirada_desviada_sostenida: 'Mirada desviada sostenida',
  perdida_de_foco: 'Pérdida de foco',
  cambio_pestana: 'Cambio de pestaña',
  monitor_adicional: 'Monitor adicional',
  salida_pantalla_completa: 'Salida de pantalla completa',
  copiar_pegar: 'Copiar / Pegar',
  corte_conectividad_prolongado: 'Corte de conectividad',
  recarga_pagina: 'Recarga de página',
  reanudacion_tardia: 'Reanudación tardía',
};

/** Tono del Badge por severidad — el color DEBE acompañar a la palabra.
 *
 * Una lista donde "alta" y "baja" se ven idénticas obliga a leer cada fila para
 * entender la gravedad. El color hace el trabajo de un vistazo, y en la pantalla
 * del alumno importa todavía más: es el material con el que puede defenderse.
 */
export const SEVERIDAD_TONE: Record<Severidad, 'neutral' | 'success' | 'warning' | 'error'> = {
  baseline: 'neutral',
  baja: 'success',
  media: 'warning',
  alta: 'error',
  critica: 'error',
};

/** Etiqueta legible de la re-inferencia server-side (RN-EV: el cliente no decide). */
export const VEREDICTO_REINFERENCIA_LABEL: Record<string, string> = {
  no_evaluado: 'No se volvió a analizar',
  coincide: 'Confirmado por el servidor',
  discrepancia: 'El servidor no coincide con lo detectado',
};

/** Etiqueta de severidad, tolerante a un valor desconocido (nunca lo muestra crudo). */
export function severidadLabel(s: string): string {
  return (SEVERIDAD_LABEL as Record<string, string>)[s]
    ?? (s ? s.charAt(0).toUpperCase() + s.slice(1) : '');
}

/** Etiqueta de tipo de evento, tolerante a un tipo que el front no conozca. */
export function tipoEventoLabel(t: string): string {
  return (TIPO_EVENTO_LABEL as Record<string, string>)[t]
    ?? (t ? t.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()) : '');
}

/** Etiqueta del veredicto de re-inferencia, sin snake_case a la vista. */
export function veredictoReinferenciaLabel(v: string): string {
  return VEREDICTO_REINFERENCIA_LABEL[v]
    ?? (v ? v.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()) : '');
}
