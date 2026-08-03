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
  // del docente a cargo: si se mandara con la cuenta institucional quedaría en la
  // libreta sin responsable, y en silencio (el docente creería que la puso él).
  sin_credencial_docente: {
    label: 'Falta conectar la cuenta del campus',
    detalle:
      'La nota se devuelve al campus con la cuenta del docente a cargo de la comisión, para que en la libreta figure quién la puso. Falta que esa comisión tenga docente asignado y que esa persona conecte su cuenta en Configuración → Campus (Moodle). Apenas la conecte, volvé a sincronizar.',
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
