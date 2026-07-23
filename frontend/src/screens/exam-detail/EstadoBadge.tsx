import { Badge } from '../../ui/components';
import type { EstadoMoodle } from '../../lib/examContentResultados';

const ESTADO_MOODLE_CONFIG: Record<EstadoMoodle, { label: string; tone: 'warning' | 'success' | 'error' | 'neutral' }> = {
  pendiente: { label: 'Pendiente de sincronizar', tone: 'warning' },
  enviado:   { label: 'Sincronizado en Moodle',  tone: 'success' },
  fallido:   { label: 'Falló',                   tone: 'error' },
  sin_token: { label: 'Sin token / no enviado',  tone: 'neutral' },
};

// Por qué la nota NO se va a mandar. Va en ROJO y PISA al estado de sincronización:
// una nota retenida figuraba como "Pendiente de sincronizar", igual que una que
// solo faltaba enviar, así que el admin apretaba Sincronizar y no entendía por qué
// esa fila no se movía. Lo que necesita ver primero es que está frenada y por qué.
const RETENCION_CONFIG: Record<string, { label: string; detalle: string }> = {
  en_riesgo: {
    label: 'Retenida · supera el umbral de riesgo',
    detalle: 'La sesión superó el umbral de riesgo y todavía no la revisó una persona. La nota no se envía hasta que haya decisión.',
  },
  caso_abierto: {
    label: 'Retenida · caso abierto',
    detalle: 'Un revisor derivó el caso y falta el veredicto. La nota no se envía hasta que se resuelva.',
  },
  anulada: {
    label: 'Anulada por fraude',
    detalle: 'El examen fue anulado por decisión humana. La nota enviada a Moodle es 0.',
  },
};

export function EstadoBadge({
  estado,
  retenidoPor,
}: {
  estado: EstadoMoodle;
  retenidoPor?: string | null;
}) {
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
  const cfg = ESTADO_MOODLE_CONFIG[estado] ?? { label: estado, tone: 'neutral' as const };
  return <Badge tone={cfg.tone} dot>{cfg.label}</Badge>;
}
