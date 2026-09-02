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
import { Card, Button, Icon, SectionTitle, Badge } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { api } from '../../lib/api';
import type { AccionPausa, PausaPendiente } from '../../lib/types';
import { formatFechaRelativa } from './helpers';
import { ModalOverlay } from '../../ui/ModalOverlay';

/** Intervalo de polling de la cola de pausas (ms). */
const POLL_MS = 4000;

export function PausasPendientes({ tutorActor }: { tutorActor?: string | null }) {
  const toast = useToast();
  const [pendientes, setPendientes] = useState<PausaPendiente[]>([]);
  // Pausas que están resolviéndose (para deshabilitar sus botones).
  const [resolviendo, setResolviendo] = useState<Set<string>>(new Set());
  // Rechazo: la pausa elegida + el motivo que el proctor escribe (obligatorio).
  const [rechazando, setRechazando] = useState<PausaPendiente | null>(null);
  const [motivoRechazo, setMotivoRechazo] = useState('');

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

  const resolver = async (pausaId: string, accion: AccionPausa, motivo?: string) => {
    setResolviendo((s) => new Set(s).add(pausaId));
    try {
      await api.resolverPausa(pausaId, accion, tutorActor ?? null, motivo ?? null);
      toastRef.current.success(accion === 'aprobar' ? 'Pausa aprobada' : 'Pausa rechazada');
      // Sacamos la pausa de la cola de inmediato (ya no está 'solicitada').
      setPendientes((prev) => prev.filter((p) => p.id !== pausaId));
    } catch (e) {
      const status = (e as { status?: number })?.status;
      if (status === 409) {
        toastRef.current.info('Esa pausa ya fue resuelta por otro tutor');
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

  // Abre el modal para capturar el motivo del rechazo (obligatorio).
  const abrirRechazo = (p: PausaPendiente) => {
    setMotivoRechazo('');
    setRechazando(p);
  };

  // Confirma el rechazo: requiere motivo no vacío. Cierra el modal al disparar.
  const confirmarRechazo = async () => {
    const motivo = motivoRechazo.trim();
    if (!motivo || !rechazando) return;
    const pausaId = rechazando.id;
    setRechazando(null);
    await resolver(pausaId, 'rechazar', motivo);
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
            <div
              key={p.id}
              className="bg-amber-50 rounded-2xl border border-amber-200 shadow-sm transition-shadow hover:shadow-md p-md space-y-sm"
            >
              <div className="flex items-start gap-sm">
                <div className="w-9 h-9 rounded-full bg-warning-container flex items-center justify-center shrink-0">
                  <Icon name="pan_tool" className="text-warning text-[18px]" fill />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-label-md font-semibold text-on-surface truncate">
                    {/* QUIÉN la pide. La etiqueta la manda el cliente y en el
                        flujo real cae al título del examen: el tutor leía
                        "Parcial 1 — Programación III pide una pausa". */}
                    {p.alumno_nombre?.trim() ||
                      p.etiqueta?.trim() ||
                      `Sesión ${p.session_id.slice(0, 8)}…`}
                  </p>
                  <p className="text-label-sm text-on-surface-variant">{formatFechaRelativa(p.solicitada_en)}</p>
                </div>
                <Badge tone="warning">Pendiente</Badge>
              </div>
              <p className="text-label-sm font-medium text-on-surface break-words">“{p.motivo}”</p>
              <div className="flex gap-base">
                <button
                  type="button"
                  onClick={() => void resolver(p.id, 'aprobar')}
                  disabled={ocupado}
                  className="flex-1 inline-flex items-center justify-center gap-base rounded-lg px-sm py-base text-label-sm font-semibold bg-success-container text-success hover:bg-success-container/70 disabled:opacity-50 transition-colors"
                >
                  <Icon name="check" className="text-[16px]" /> Aprobar
                </button>
                <button
                  type="button"
                  onClick={() => abrirRechazo(p)}
                  disabled={ocupado}
                  className="flex-1 inline-flex items-center justify-center gap-base rounded-lg px-sm py-base text-label-sm font-semibold bg-error-container text-on-error-container hover:bg-error-container/70 disabled:opacity-50 transition-colors"
                >
                  <Icon name="close" className="text-[16px]" /> Rechazar
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Modal para capturar el MOTIVO del rechazo (obligatorio). El alumno lo
          verá en pantalla, así que pedimos un texto claro y no vacío. */}
      {rechazando && (
        <ModalOverlay etiqueta="Rechazar pausa" onCerrar={() => setRechazando(null)}>
          <Card className="max-w-md w-full space-y-md">
            <div className="space-y-base">
              <h3 className="font-headline text-headline-md text-on-surface">Rechazar pausa</h3>
              <p className="text-label-sm text-on-surface-variant">
                Explicá brevemente por qué no autorizás la pausa. El alumno verá este
                mensaje en su pantalla.
              </p>
              <p className="text-label-sm text-on-surface bg-surface-container-low rounded-lg px-sm py-base">
                <span className="text-on-surface-variant">Pedido del alumno: </span>
                {rechazando.motivo}
              </p>
            </div>
            <textarea
              value={motivoRechazo}
              onChange={(e) => setMotivoRechazo(e.target.value)}
              rows={3}
              autoFocus
              maxLength={500}
              placeholder="Ej.: estás en mitad de una pregunta; esperá a terminarla."
              className="w-full px-sm py-base text-label-md rounded-xl border border-outline-variant bg-surface-container-lowest focus:border-primary-container outline-none resize-none"
            />
            <div className="flex gap-base justify-end">
              <Button variant="outline" size="sm" onClick={() => setRechazando(null)}>
                Cancelar
              </Button>
              <Button
                variant="danger"
                size="sm"
                icon="close"
                onClick={() => void confirmarRechazo()}
                disabled={!motivoRechazo.trim()}
              >
                Rechazar pausa
              </Button>
            </div>
          </Card>
        </ModalOverlay>
      )}
    </section>
  );
}

export default PausasPendientes;
