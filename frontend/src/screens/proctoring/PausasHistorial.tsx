/**
 * PausasHistorial — Historial de TODAS las pausas de una sesión (solo lectura).
 *
 * Para el detalle de una sesión GRABADA: el revisor lee como evidencia qué pausas
 * pidió el alumno, cuándo, con qué motivo, y cómo se resolvieron (aprobada /
 * rechazada con su motivo / finalizada). No es accionable — la sesión ya terminó.
 *
 * L2.5: es contexto para la revisión humana, no un veredicto.
 */
import { useEffect, useState } from 'react';
import { Card, Icon, SectionTitle, Badge } from '../../ui/components';
import { api } from '../../lib/api';
import type { EstadoPausa, Pausa } from '../../lib/types';
import { formatFecha } from './helpers';

const ESTADO: Record<
  EstadoPausa,
  { tone: 'success' | 'error' | 'neutral' | 'warning'; label: string; card: string; icon: string; text: string; iconBg: string }
> = {
  solicitada: { tone: 'warning', label: 'Quedó pendiente', card: 'bg-amber-50 border-amber-200', icon: 'pan_tool', text: 'text-warning', iconBg: 'bg-warning-container' },
  aprobada: { tone: 'success', label: 'Aprobada', card: 'bg-green-50 border-green-200', icon: 'check_circle', text: 'text-success', iconBg: 'bg-success-container' },
  rechazada: { tone: 'error', label: 'Rechazada', card: 'bg-red-50 border-red-200', icon: 'cancel', text: 'text-on-error-container', iconBg: 'bg-error-container' },
  finalizada: { tone: 'neutral', label: 'Finalizada', card: 'bg-surface-container-low border-surface-200', icon: 'history', text: 'text-on-surface-variant', iconBg: 'bg-surface-container-high' },
  // El sistema la cerró por timeout / fin de sesión sin respuesta del proctor
  // (C-72 sección 12). Tono neutro: NO es un veredicto (L2.5), solo caducó.
  expirada: { tone: 'neutral', label: 'No respondida a tiempo', card: 'bg-surface-container-low border-surface-200', icon: 'timer_off', text: 'text-on-surface-variant', iconBg: 'bg-surface-container-high' },
};

/** Card tintada con el color suave del estado (no blanca). */
const CARD_BASE = 'rounded-2xl border shadow-sm transition-shadow hover:shadow-md p-md space-y-sm';

export function PausasHistorial({ sessionId }: { sessionId: string }) {
  const [pausas, setPausas] = useState<Pausa[]>([]);
  const [cargado, setCargado] = useState(false);

  useEffect(() => {
    let vivo = true;
    api
      .listarPausas(sessionId)
      .then((data) => { if (vivo) setPausas(data); })
      .catch(() => { /* degradación silenciosa */ })
      .finally(() => { if (vivo) setCargado(true); });
    return () => { vivo = false; };
  }, [sessionId]);

  // No renderizar nada si no hubo pausas (no ensuciar la evidencia con un vacío).
  if (cargado && pausas.length === 0) return null;

  return (
    <Card className="space-y-md">
      <SectionTitle
        sub={`${pausas.length} ${pausas.length === 1 ? 'solicitud' : 'solicitudes'} del estudiante`}
      >
        Solicitudes de pausa
      </SectionTitle>

      <div className="space-y-sm">
        {pausas.map((p) => {
          const est = ESTADO[p.estado];
          return (
            <div key={p.id} className={`${CARD_BASE} ${est.card}`}>
              <div className="flex items-center gap-sm">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${est.iconBg}`}>
                  <Icon name={est.icon} className={`text-[18px] ${est.text}`} fill />
                </div>
                <span className="flex-1 min-w-0 text-label-sm font-medium text-on-surface">
                  Solicitada el {formatFecha(p.solicitada_en, false)}
                </span>
                <Badge tone={est.tone}>{est.label}</Badge>
              </div>

              {/* Lo que escribió el alumno — cita textual entre comillas */}
              <p className="text-label-md font-medium text-on-surface break-words">“{p.motivo}”</p>

              {p.estado === 'rechazada' && p.motivo_rechazo && (
                <p className="text-label-sm text-on-surface-variant break-words">
                  <span className="font-medium text-on-surface">Respuesta del tutor: </span>
                  {p.motivo_rechazo}
                </p>
              )}

              {(p.resuelta_en || p.tutor_actor) && (
                <p className="text-[11px] text-on-surface-variant">
                  Resuelta {p.resuelta_en ? `el ${formatFecha(p.resuelta_en, false)}` : ''}
                  {p.tutor_actor ? ` · por ${p.tutor_actor}` : ''}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export default PausasHistorial;
