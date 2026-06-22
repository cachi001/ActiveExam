/**
 * PausasPendientes — Cola de solicitudes de pausa a nivel panel del PROCTOR (C-15).
 *
 * Pollea `listarPausasPendientes()` (solo estado 'solicitada', de todas las
 * sesiones) cada POLL_MS. Cada solicitud muestra etiqueta/sesión + motivo + hace
 * cuánto, con botones Aprobar / Rechazar → `resolverPausa(id, accion, actor)`.
 *
 * Maneja el 409 (otra persona ya resolvió la pausa) con un toast suave y refresh,
 * en vez de un error duro. No se renderiza nada si no hay pendientes.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Card, Button, Icon, SectionTitle } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { api } from '../../lib/api';
import type { AccionPausa, PausaPendiente } from '../../lib/types';
import { formatFechaRelativa } from './helpers';

/** Intervalo de polling de la cola de pausas (ms). */
const POLL_MS = 4000;

export function PausasPendientes({ proctorActor }: { proctorActor?: string | null }) {
  const toast = useToast();
  const [pendientes, setPendientes] = useState<PausaPendiente[]>([]);
  // Pausas que están resolviéndose (para deshabilitar sus botones).
  const [resolviendo, setResolviendo] = useState<Set<string>>(new Set());

  const enVuelo = useRef(false);
  const toastRef = useRef(toast);
  toastRef.current = toast;

  const refrescar = useCallback(async () => {
    if (enVuelo.current) return;
    enVuelo.current = true;
    try {
      const data = await api.listarPausasPendientes();
      setPendientes(data);
    } catch {
      // Degradación silenciosa: no rompemos el loop ni la última data.
    } finally {
      enVuelo.current = false;
    }
  }, []);

  // Polling con cleanup (mismo patrón que Proctor.tsx).
  useEffect(() => {
    void refrescar();
    const id = setInterval(() => void refrescar(), POLL_MS);
    return () => clearInterval(id);
  }, [refrescar]);

  const resolver = async (pausaId: string, accion: AccionPausa) => {
    setResolviendo((s) => new Set(s).add(pausaId));
    try {
      await api.resolverPausa(pausaId, accion, proctorActor ?? null);
      toastRef.current.success(accion === 'aprobar' ? 'Pausa aprobada' : 'Pausa rechazada');
      // Sacamos la pausa de la cola de inmediato (ya no está 'solicitada').
      setPendientes((prev) => prev.filter((p) => p.id !== pausaId));
    } catch (e) {
      const status = (e as { status?: number })?.status;
      if (status === 409) {
        toastRef.current.info('Esa pausa ya fue resuelta por otro proctor');
      } else {
        toastRef.current.error('No se pudo resolver la pausa');
      }
      void refrescar();
    } finally {
      setResolviendo((s) => {
        const next = new Set(s);
        next.delete(pausaId);
        return next;
      });
    }
  };

  if (pendientes.length === 0) return null;

  return (
    <section className="space-y-md">
      <SectionTitle
        sub={`${pendientes.length} ${pendientes.length === 1 ? 'solicitud pendiente' : 'solicitudes pendientes'}`}
      >
        Solicitudes de pausa
      </SectionTitle>
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-md">
        {pendientes.map((p) => {
          const ocupado = resolviendo.has(p.id);
          return (
            <Card key={p.id} className="space-y-sm border-l-4 border-l-warning">
              <div className="flex items-start gap-base">
                <Icon name="pan_tool" className="text-warning text-[20px] shrink-0 mt-px" fill />
                <div className="min-w-0 flex-1">
                  <p className="text-label-md font-semibold text-on-surface truncate">
                    {p.etiqueta?.trim() || `Sesión ${p.session_id.slice(0, 8)}…`}
                  </p>
                  <p className="text-label-sm text-on-surface-variant">{formatFechaRelativa(p.solicitada_en)}</p>
                </div>
              </div>
              <p className="text-label-sm text-on-surface bg-surface-container-low rounded-lg px-sm py-base">
                <span className="text-on-surface-variant">Motivo: </span>
                {p.motivo}
              </p>
              <div className="flex gap-base">
                <Button
                  variant="success"
                  size="sm"
                  icon="check"
                  className="flex-1"
                  onClick={() => void resolver(p.id, 'aprobar')}
                  disabled={ocupado}
                >
                  Aprobar
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  icon="close"
                  className="flex-1"
                  onClick={() => void resolver(p.id, 'rechazar')}
                  disabled={ocupado}
                >
                  Rechazar
                </Button>
              </div>
            </Card>
          );
        })}
      </div>
    </section>
  );
}

export default PausasPendientes;
