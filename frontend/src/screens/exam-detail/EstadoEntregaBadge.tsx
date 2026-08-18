import { Badge } from '../../ui/components';
import type { EstadoEntrega } from '../../lib/examContentResultados';

// C-76 tarea 14: estado de la ENTREGA (derivado server-side), ORTOGONAL al
// estado de sync a Moodle (`EstadoBadge.tsx`). Labels en español CLARO — nunca
// el nombre técnico crudo (nada de "en_revision" a la vista del usuario).
export const ESTADO_ENTREGA_CONFIG: Record<
  EstadoEntrega,
  { label: string; tone: 'warning' | 'success' | 'error' | 'neutral' }
> = {
  no_finalizada: { label: 'No finalizada',           tone: 'neutral' },
  en_revision:   { label: 'Pendiente de revisión',   tone: 'error' },
  revisada:      { label: 'Revisada',                tone: 'success' },
  finalizada:    { label: 'Finalizada',              tone: 'success' },
};

// Opciones del select de filtro — mismo orden que el flujo natural de una
// entrega (no finalizada -> en revisión -> revisada/finalizada).
export const ESTADO_ENTREGA_OPCIONES: { value: EstadoEntrega; label: string }[] = [
  { value: 'no_finalizada', label: 'No finalizada' },
  { value: 'en_revision',   label: 'Pendiente de revisión' },
  { value: 'revisada',      label: 'Revisada' },
  { value: 'finalizada',    label: 'Finalizada' },
];

export function EstadoEntregaBadge({ estado }: { estado?: EstadoEntrega }) {
  // Ausente (fixtures/respuestas viejas) -> tratar como 'finalizada' (caso base).
  const cfg = ESTADO_ENTREGA_CONFIG[estado ?? 'finalizada'] ?? {
    label: estado ?? 'finalizada',
    tone: 'neutral' as const,
  };
  return <Badge tone={cfg.tone} dot>{cfg.label}</Badge>;
}
