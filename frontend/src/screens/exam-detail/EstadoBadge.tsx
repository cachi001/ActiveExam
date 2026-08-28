import type { ReactNode } from 'react';
import { Badge } from '../../ui/components';
import type { EstadoMoodle } from '../../lib/examContentResultados';
import { useEstadosMoodle } from './useEstadosMoodle';
import { useRetenciones } from './useCatalogosNota';

// Por qué la nota NO se va a mandar. Va en color y PISA al estado de entrega:
// una nota retenida figuraba como "Pendiente de sincronizar", igual que una que
// solo faltaba enviar, así que el admin apretaba Sincronizar y no entendía por
// qué esa fila no se movía. Lo que necesita ver primero es que está frenada.
//
// Los TEXTOS ya no están acá: los define el backend (`retenciones_para_ui`).
// Escritos en la pantalla, divergían de lo que decía el archivo.

// Motivos que hablan de la INTEGRIDAD de la nota, no de si se puede enviar.
// Estos pisan a cualquier estado: una nota anulada por fraude sigue anulada
// aunque alguien la haya cargado a mano en el campus.
//
// Los otros dos (sin_destino, sin_credencial_docente) explican por qué la nota
// no SALE. Cuando ya la cargó una persona, esa explicación dejó de aplicar: la
// fila decía "Falta conectar el campus" sobre una nota que ya estaba en la
// libreta, y mandaba al docente a resolver algo que ya no hacía falta.
const RETENCIONES_QUE_SIGUEN_MANDANDO = new Set(['en_riesgo', 'anulada']);

export function EstadoBadge({
  estado,
  retenidoPor,
  retenciones: retencionesFila,
  marcadaManualPor,
  marcadaManualEn,
}: {
  estado: EstadoMoodle;
  /** El motivo principal. Se conserva para las filas que no traen la lista. */
  retenidoPor?: string | null;
  /** Todos los motivos que la retienen, del más importante al menos. */
  retenciones?: string[];
  /** c-78 D14: quién afirmó que cargó la nota a mano, y cuándo. */
  marcadaManualPor?: string | null;
  marcadaManualEn?: string | null;
}) {
  // La etiqueta y el color, siempre del backend (fuente única).
  const estados = useEstadosMoodle();
  const retenciones = useRetenciones();
  // UN estado, el del enum del backend (pendiente | enviado | fallido |
  // sin_token | manual). El motivo NO es un estado: "falta el destino" explica
  // POR QUÉ la nota sigue pendiente, y ponerlo en lugar del estado dejaba la
  // columna diciendo cosas que el enum no tiene.
  //
  // "anulada" tampoco va acá: lo que se anula es el RESULTADO. La nota anulada
  // igual se entrega al campus — `anular_nota` escribe 0 en la libreta.
  const motivo = (retencionesFila ?? (retenidoPor ? [retenidoPor] : []))
    .filter((m) => m !== 'anulada')
    // Una nota ya cargada a mano no espera que se configure nada.
    .filter((m) => estado !== 'manual' || RETENCIONES_QUE_SIGUEN_MANDANDO.has(m))[0];
  const detalleMotivo = motivo ? retenciones.get(motivo) : undefined;

  // Si algo la traba, la entrega FALLÓ: ese es el estado, y el motivo va abajo.
  // Antes el chip mostraba el motivo EN LUGAR del estado ("Falta conectar el
  // campus"), así que la columna de estado no decía en qué estado estaba.
  const valorMostrado = motivo ? 'fallido' : estado;
  const info = estados.find((e) => e.valor === valorMostrado);
  const cfg = { label: info?.etiqueta ?? valorMostrado, tone: info?.tono ?? ('neutral' as const) };

  // El motivo va DEBAJO del estado, en chico. No lo reemplaza: son dos cosas
  // (dónde está la nota, y qué la traba). Y no se repite cuando dice lo mismo
  // que el estado — con el campus sin conectar, ambos dirían igual.
  const bajoElChip = detalleMotivo;
  // El motivo va debajo del chip, sin marco: es una aclaración, no otra caja.
  // Con borde y fondo parecía un cuadro dentro de la celda.
  const conMotivo = (chip: ReactNode, titulo?: string) =>
    bajoElChip ? (
      <span
        className="inline-flex flex-col items-start gap-1"
        title={titulo ?? bajoElChip.detalle}
      >
        {chip}
        <span className="text-[11px] leading-tight text-on-surface-variant">
          {bajoElChip.etiqueta}
        </span>
      </span>
    ) : (
      <span title={titulo}>{chip}</span>
    );

  if (estado === 'manual') {
    // El ORIGEN del estado tiene que estar a la vista: "marcado por X el Y" no
    // es lo mismo que "confirmado por el campus".
    const cuando = marcadaManualEn
      ? new Date(marcadaManualEn).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })
      : null;
    const detalle = marcadaManualPor
      ? `Marcada a mano por ${marcadaManualPor}${cuando ? ` el ${cuando}` : ''}. El campus no confirmó el envío.`
      : 'Marcada a mano. El campus no confirmó el envío.';
    return conMotivo(<Badge tone={cfg.tone}>{cfg.label}</Badge>, detalle);
  }
  return conMotivo(<Badge tone={cfg.tone}>{cfg.label}</Badge>);
}
