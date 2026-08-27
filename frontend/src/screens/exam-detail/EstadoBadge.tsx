import { Badge } from '../../ui/components';
import type { EstadoMoodle } from '../../lib/examContentResultados';
import { useEstadosMoodle } from './useEstadosMoodle';

// Por qué la nota NO se va a mandar. Va en ROJO y PISA al estado de sincronización:
// una nota retenida figuraba como "Pendiente de sincronizar", igual que una que
// solo faltaba enviar, así que el admin apretaba Sincronizar y no entendía por qué
// esa fila no se movía. Lo que necesita ver primero es que está frenada y por qué.
const RETENCION_CONFIG: Record<string, { label: string; detalle: string }> = {
  en_riesgo: {
    label: 'Retenida · supera el umbral de riesgo',
    detalle: 'La sesión superó el umbral de riesgo y todavía no la revisó una persona. La nota no se envía hasta que haya decisión.',
  },
  anulada: {
    label: 'Anulada por fraude',
    detalle: 'El examen fue anulado por decisión humana. La nota enviada a Moodle es 0.',
  },
  // No es una retención por revisión: es configuración que falta. Se muestra igual
  // de visible porque el efecto es el mismo (la nota no llega a la libreta) y antes
  // esto no se veía: la nota se escribía en el curso global, o sea en otra materia.
  sin_destino: {
    label: 'Falta el destino en el campus',
    detalle:
      'Este examen no tiene cargado el curso y la actividad de Moodle donde va la nota. Configuralos en el examen (sección «Destino en Moodle») y volvé a sincronizar.',
  },
  // Tampoco es una retención por revisión. La nota SIEMPRE se devuelve con la cuenta
  // del tutor a cargo: si se mandara con la cuenta institucional quedaría en la
  // libreta sin responsable, y en silencio (el docente creería que la puso él).
  sin_credencial_docente: {
    label: 'Falta conectar la cuenta del campus',
    detalle:
      'La nota se devuelve al campus con la cuenta del tutor a cargo de la comisión, para que en la libreta figure quién la puso. Falta que esa comisión tenga tutor asignado y que esa persona conecte su cuenta en Configuración → Campus (Moodle). Apenas la conecte, volvé a sincronizar.',
  },
};

export function EstadoBadge({
  estado,
  retenidoPor,
  marcadaManualPor,
  marcadaManualEn,
}: {
  estado: EstadoMoodle;
  retenidoPor?: string | null;
  /** c-78 D14: quién afirmó que cargó la nota a mano, y cuándo. */
  marcadaManualPor?: string | null;
  marcadaManualEn?: string | null;
}) {
  // La etiqueta y el color de cada estado los define el backend (fuente única).
  const estados = useEstadosMoodle();
  if (retenidoPor) {
    const ret = RETENCION_CONFIG[retenidoPor] ?? {
      label: 'Retenida por revisión',
      detalle: 'La nota no se sincroniza hasta que se resuelva la revisión.',
    };
    return (
      <span title={ret.detalle}>
        <Badge tone="error" dot>{ret.label}</Badge>
      </span>
    );
  }
  const info = estados.find((e) => e.valor === estado);
  const cfg = { label: info?.etiqueta ?? estado, tone: info?.tono ?? ('neutral' as const) };
  if (estado === 'manual') {
    // El ORIGEN del estado tiene que estar a la vista: "marcado por X el Y" no
    // es lo mismo que "confirmado por el campus".
    const cuando = marcadaManualEn
      ? new Date(marcadaManualEn).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })
      : null;
    const detalle = marcadaManualPor
      ? `Marcada a mano por ${marcadaManualPor}${cuando ? ` el ${cuando}` : ''}. El campus no confirmó el envío.`
      : 'Marcada a mano. El campus no confirmó el envío.';
    return (
      <span title={detalle}>
        <Badge tone={cfg.tone} dot>{cfg.label}</Badge>
      </span>
    );
  }
  return <Badge tone={cfg.tone} dot>{cfg.label}</Badge>;
}
