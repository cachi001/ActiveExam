/**
 * PausaSesionPanel — Solicitud de pausa de UNA sesión, dentro de su detalle (C-15).
 *
 * Complementa a `PausasPendientes` (cola global del panel del proctor): cuando el
 * proctor entra al detalle de una sesión en vivo, ve y resuelve acá mismo la pausa
 * que pide ESE alumno, sin tener que volver al panel.
 *
 * Pollea `listarPausas(sessionId)` cada POLL_MS y se queda con la pausa relevante:
 * la 'solicitada' (pendiente de resolver) o la 'aprobada' en curso. Si no hay
 * ninguna, no renderiza nada (no ensucia el detalle).
 *
 * L2.5: resolver una pausa es operativo (autoriza/deniega un descanso), NO un
 * veredicto disciplinario.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Card, Button, Icon } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { api } from '../../lib/api';
import type { AccionPausa, Pausa } from '../../lib/types';
import { formatFechaRelativa } from './helpers';

const POLL_MS = 4000;

export function PausaSesionPanel({
  sessionId,
  proctorActor,
}: {
  sessionId: string;
  proctorActor?: string | null;
}) {
  const toast = useToast();
  const [pausa, setPausa] = useState<Pausa | null>(null);
  const [resolviendo, setResolviendo] = useState(false);
  const [rechazando, setRechazando] = useState(false);
  const [motivoRechazo, setMotivoRechazo] = useState('');

  const enVuelo = useRef(false);
  const toastRef = useRef(toast);
  toastRef.current = toast;

  const refrescar = useCallback(async () => {
    if (enVuelo.current) return;
    enVuelo.current = true;
    try {
      const lista = await api.listarPausas(sessionId);
      // La lista viene desc por solicitada_en. Priorizamos la solicitada (acción
      // pendiente); si no hay, mostramos la aprobada en curso (informativa).
      const solicitada = lista.find((p) => p.estado === 'solicitada');
      const enCurso = lista.find((p) => p.estado === 'aprobada' && !p.fin_en);
      setPausa(solicitada ?? enCurso ?? null);
    } catch {
      // Degradación silenciosa: el próximo tick reintenta.
    } finally {
      enVuelo.current = false;
    }
  }, [sessionId]);

  useEffect(() => {
    void refrescar();
    const id = setInterval(() => void refrescar(), POLL_MS);
    return () => clearInterval(id);
  }, [refrescar]);

  const resolver = async (accion: AccionPausa, motivo?: string) => {
    if (!pausa) return;
    setResolviendo(true);
    try {
      await api.resolverPausa(pausa.id, accion, proctorActor ?? null, motivo ?? null);
      toastRef.current.success(accion === 'aprobar' ? 'Pausa aprobada' : 'Pausa rechazada');
      void refrescar();
    } catch (e) {
      const status = (e as { status?: number })?.status;
      if (status === 409) {
        toastRef.current.info('Esa pausa ya fue resuelta');
      } else {
        toastRef.current.error('No se pudo resolver la pausa');
      }
      void refrescar();
    } finally {
      setResolviendo(false);
    }
  };

  const confirmarRechazo = async () => {
    const motivo = motivoRechazo.trim();
    if (!motivo) return;
    setRechazando(false);
    await resolver('rechazar', motivo);
    setMotivoRechazo('');
  };

  if (!pausa) return null;

  const enCurso = pausa.estado === 'aprobada';

  return (
    <Card
      className={`space-y-md border-l-4 ${enCurso ? 'border-l-success bg-success-container/25' : 'border-l-warning bg-warning-container/40'}`}
    >
      <div className="flex items-start gap-sm">
        <Icon
          name={enCurso ? 'pause_circle' : 'pan_tool'}
          className={`${enCurso ? 'text-success' : 'text-warning'} text-[22px] shrink-0 mt-px`}
          fill
        />
        <div className="min-w-0 flex-1">
          <p className="font-headline text-title-md text-on-surface">
            {enCurso ? 'Pausa en curso' : 'El alumno solicita una pausa'}
          </p>
          <p className="text-label-sm text-on-surface-variant">
            {enCurso ? 'Aprobada ' : 'Solicitada '}
            {formatFechaRelativa((enCurso && pausa.inicio_en) || pausa.solicitada_en)}
          </p>
        </div>
      </div>

      <p className="text-label-md text-on-surface bg-white/60 rounded-lg px-sm py-base">
        <span className="text-on-surface-variant">Motivo: </span>
        {pausa.motivo}
      </p>

      {!enCurso && (
        <div className="flex gap-base">
          <Button
            variant="success"
            size="sm"
            icon="check"
            className="flex-1"
            onClick={() => void resolver('aprobar')}
            disabled={resolviendo}
          >
            Aprobar pausa
          </Button>
          <Button
            variant="danger"
            size="sm"
            icon="close"
            className="flex-1"
            onClick={() => { setMotivoRechazo(''); setRechazando(true); }}
            disabled={resolviendo}
          >
            Rechazar
          </Button>
        </div>
      )}

      {/* Modal de motivo del rechazo (obligatorio; el alumno lo verá). */}
      {rechazando && (
        <div className="fixed inset-0 z-[95] bg-inverse-surface/60 backdrop-blur-sm flex items-center justify-center p-lg animate-in fade-in">
          <Card className="max-w-md w-full space-y-md">
            <div className="space-y-base">
              <h3 className="font-headline text-headline-md text-on-surface">Rechazar pausa</h3>
              <p className="text-label-sm text-on-surface-variant">
                Explicá brevemente por qué no autorizás la pausa. El alumno verá este
                mensaje en su pantalla.
              </p>
              <p className="text-label-sm text-on-surface bg-surface-container-low rounded-lg px-sm py-base">
                <span className="text-on-surface-variant">Pedido del alumno: </span>
                {pausa.motivo}
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
              <Button variant="outline" size="sm" onClick={() => setRechazando(false)}>
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
        </div>
      )}
    </Card>
  );
}

export default PausaSesionPanel;
