/**
 * DetectoresSelector — selector de detectores activos.
 *
 * C-68 UX (D): cards con gap correcto, padding interno cómodo, switch alineado
 * a la derecha, nombre+descripción a la izquierda. Que respiren.
 */
import { TIPO_EVENTO_LABEL } from '../../../lib/api';
import { Icon } from '../../../ui/components';
import type { TipoEvento } from '../../../lib/types';

// Eventos que capturan un SCREENSHOT cuando se disparan (el frame de la cámara ES
// la prueba). El resto NO adjunta imagen — el registro del evento + timestamp ya es
// la evidencia (privacidad L2.5 / regla dura #7). DEBE coincidir con
// EVENTOS_CON_EVIDENCIA_VISUAL en useExamProctoring.ts.
const CAPTURA_SCREENSHOT: Set<string> = new Set([
  'rostro_ausente',
  'multiples_rostros',
  'mirada_desviada_sostenida',
]);

// Orden por grupos lógicos: primero lo que ve la cámara, después el
// comportamiento en el navegador, y al final hardware/conectividad.
// `as const`: sin esto, (typeof DETECTORES)[number] se ensancha al union
// COMPLETO TipoEvento (incluidos recarga_pagina/reanudacion_tardia/captura_pausa,
// que son eventos emitidos por el servidor, no detectores toggleables) y
// DETECTOR_DESC de abajo terminaría exigiendo descripciones para eventos que
// nunca se muestran acá.
const DETECTORES = [
  // Cámara / visión
  'rostro_ausente',
  'multiples_rostros',
  'mirada_desviada_sostenida',
  // Navegador / contexto del examen
  'perdida_de_foco',
  'cambio_pestana',
  'salida_pantalla_completa',
  'copiar_pegar',
  // Hardware / conectividad
  'monitor_adicional',
  'corte_conectividad_prolongado',
] as const satisfies readonly TipoEvento[];

// Descripciones cortas y claras (para NO técnicos) de qué vigila cada detector.
// Record<(typeof DETECTORES)[number], string>: si se agrega un detector a
// DETECTORES y se olvida su descripción acá, TypeScript lo marca como error
// (a diferencia de Record<string, string>, que dejaba pasar claves faltantes
// en silencio — el fallback `?? ''` de abajo las ocultaba sin avisar).
const DETECTOR_DESC: Record<(typeof DETECTORES)[number], string> = {
  rostro_ausente: 'No se ve ningún rostro frente a la cámara.',
  multiples_rostros: 'Aparece más de una persona en cámara.',
  mirada_desviada_sostenida: 'La mirada se va de la pantalla por un rato.',
  perdida_de_foco: 'La ventana del examen deja de estar activa.',
  monitor_adicional: 'Se detecta una segunda pantalla conectada.',
  cambio_pestana: 'El alumno cambia a otra pestaña o ventana.',
  salida_pantalla_completa: 'Se sale del modo pantalla completa.',
  copiar_pegar: 'Se usa copiar o pegar durante el examen.',
  corte_conectividad_prolongado: 'Se corta la conexión por un tiempo prolongado.',
};

interface DetectoresSelectorProps {
  value: TipoEvento[];
  onChange: (detectores: TipoEvento[]) => void;
}

export default function DetectoresSelector({ value, onChange }: DetectoresSelectorProps) {
  const toggle = (d: TipoEvento) => {
    onChange(value.includes(d) ? value.filter((x) => x !== d) : [...value, d]);
  };

  return (
    <div className="space-y-3 min-w-0">
      <p className="text-label-sm text-on-surface-variant">
        <span className="font-semibold text-on-surface">{value.length}</span> de {DETECTORES.length} detectores activos
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {DETECTORES.map((d) => {
          const on = value.includes(d);
          return (
            <button
              key={d}
              type="button"
              role="switch"
              aria-checked={on}
              aria-label={`${TIPO_EVENTO_LABEL[d]} — ${on ? 'activado' : 'desactivado'}`}
              onClick={() => toggle(d)}
              className={`group flex items-center gap-3 px-4 py-3 rounded-md border text-left transition-colors min-w-0 focus:outline-none focus:ring-2 focus:ring-outline-variant ${
                on
                  ? 'bg-surface-container-lowest border-outline-variant hover:border-outline'
                  : 'bg-surface-container-low border-outline-variant'
              }`}
            >
              {/* Nombre + descripción + si captura imagen, a la izquierda */}
              <div className="flex-1 min-w-0">
                <p className="text-label-md font-semibold text-on-surface truncate">
                  {TIPO_EVENTO_LABEL[d]}
                </p>
                <p className="text-[11px] text-on-surface-variant leading-snug mt-0.5">
                  {DETECTOR_DESC[d] ?? ''}
                </p>
                <span
                  className={`mt-1.5 inline-flex items-center gap-1 text-[10px] font-medium rounded-full px-2 py-0.5 ${
                    CAPTURA_SCREENSHOT.has(d)
                      ? 'bg-primary-fixed text-primary'
                      : 'bg-surface-container text-on-surface-variant'
                  }`}
                >
                  <Icon
                    name={CAPTURA_SCREENSHOT.has(d) ? 'photo_camera' : 'no_photography'}
                    className="text-[12px]"
                  />
                  {CAPTURA_SCREENSHOT.has(d) ? 'Captura imagen' : 'Sin imagen'}
                </span>
              </div>
              {/* Switch a la derecha (presentacional; el click es del botón contenedor) */}
              <span
                className={`relative shrink-0 inline-flex h-6 w-11 rounded-full border-2 border-transparent transition-colors duration-200 ${
                  on ? 'bg-success-600' : 'bg-outline'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform duration-200 ${
                    on ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
