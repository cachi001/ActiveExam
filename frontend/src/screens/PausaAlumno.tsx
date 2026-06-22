/**
 * PausaAlumno — Flujo de pausa autorizada del lado del ESTUDIANTE (C-15).
 *
 * El alumno solicita una pausa (con motivo); el proctor la aprueba/rechaza desde
 * su panel. Esta UI pollea `listarPausas(sessionId)` y refleja el estado de la
 * pausa más reciente:
 *   - solicitada → "Esperando aprobación del proctor…"
 *   - aprobada   → banner de PAUSA ACTIVA bien visible + timer + "Reanudar examen"
 *   - rechazada  → toast (una vez) y vuelta al estado normal
 *   - finalizada → estado normal
 *
 * IMPORTANTE (decisión de producto, Opción 1): la detección NO se apaga durante
 * la pausa. El cliente sigue siendo sensor; el backend contextualiza los eventos
 * (flag en_pausa_autorizada) y los excluye del score. Este componente solo toca UI.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Card, Button, Icon } from '../ui/components';
import { useToast } from '../ui/toast';
import { api } from '../lib/api';
import type { Pausa } from '../lib/types';

/** Intervalo de polling del estado de la pausa (ms). */
const POLL_MS = 3500;

/** Formatea segundos transcurridos como mm:ss. */
function mmss(totalSeg: number): string {
  const s = Math.max(0, Math.floor(totalSeg));
  const mm = String(Math.floor(s / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

export function PausaAlumno({ sessionId }: { sessionId: string | null | undefined }) {
  const toast = useToast();
  const [pausa, setPausa] = useState<Pausa | null>(null);
  const [pidiendo, setPidiendo] = useState(false);
  const [reanudando, setReanudando] = useState(false);
  const [transcurrido, setTranscurrido] = useState(0);
  const [modalMotivo, setModalMotivo] = useState(false);
  const [motivo, setMotivo] = useState('');

  const enVuelo = useRef(false);
  // Para avisar UNA sola vez del rechazo (el poll seguiría devolviendo la pausa).
  const rechazoAvisado = useRef<string | null>(null);

  const refrescar = useCallback(async () => {
    if (!sessionId || enVuelo.current) return;
    enVuelo.current = true;
    try {
      const lista = await api.listarPausas(sessionId);
      // La más reciente es la primera (el backend ordena desc por solicitada_en).
      const actual = lista[0] ?? null;
      setPausa(actual);
      if (actual?.estado === 'rechazada' && rechazoAvisado.current !== actual.id) {
        rechazoAvisado.current = actual.id;
        toast.error('El proctor rechazó la pausa');
      }
    } catch {
      // Degradación silenciosa.
    } finally {
      enVuelo.current = false;
    }
  }, [sessionId, toast]);

  // Polling con cleanup.
  useEffect(() => {
    if (!sessionId) return;
    void refrescar();
    const id = setInterval(() => void refrescar(), POLL_MS);
    return () => clearInterval(id);
  }, [sessionId, refrescar]);

  // Timer de la pausa activa: cuenta desde inicio_en (fuente: backend).
  const activa = pausa?.estado === 'aprobada';
  const inicioEn = pausa?.inicio_en ?? null;
  useEffect(() => {
    if (!activa || !inicioEn) {
      setTranscurrido(0);
      return;
    }
    const inicio = new Date(inicioEn).getTime();
    const tick = () => setTranscurrido((Date.now() - inicio) / 1000);
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [activa, inicioEn]);

  const abrirSolicitud = () => {
    setMotivo('');
    setModalMotivo(true);
  };

  const confirmarSolicitud = async () => {
    const m = motivo.trim();
    if (!m || !sessionId || pidiendo) return;
    setPidiendo(true);
    try {
      const p = await api.solicitarPausa(sessionId, m);
      setPausa(p);
      setModalMotivo(false);
      toast.info('Solicitud de pausa enviada al proctor');
    } catch {
      toast.error('No se pudo solicitar la pausa');
    } finally {
      setPidiendo(false);
    }
  };

  const reanudar = async () => {
    if (!pausa || reanudando) return;
    setReanudando(true);
    try {
      const p = await api.finalizarPausa(pausa.id);
      setPausa(p);
      toast.success('Examen reanudado');
    } catch {
      toast.error('No se pudo reanudar el examen');
      void refrescar();
    } finally {
      setReanudando(false);
    }
  };

  const estado = pausa?.estado;
  const esperando = estado === 'solicitada';

  return (
    <>
      <Card className="space-y-sm">
        <h3 className="text-label-md font-bold text-on-surface border-b border-outline-variant/40 pb-base">
          Pausa autorizada
        </h3>

        {esperando ? (
          <div className="flex items-center gap-sm text-on-surface-variant py-base">
            <Icon name="hourglass_top" className="text-[20px] text-warning ae-spin" />
            <p className="text-label-sm">Esperando aprobación del proctor…</p>
          </div>
        ) : activa ? (
          <p className="text-label-sm text-on-surface-variant">
            Tenés una pausa autorizada en curso. Reanudá el examen cuando estés listo/a.
          </p>
        ) : (
          <>
            <p className="text-label-sm text-on-surface-variant">
              Si necesitás interrumpir el examen (ir al baño, una urgencia), pedí una pausa.
              El proctor la aprueba; durante la pausa la supervisión sigue activa.
            </p>
            <Button variant="outline" size="sm" icon="pause_circle" onClick={abrirSolicitud}>
              Solicitar pausa
            </Button>
          </>
        )}
      </Card>

      {/* Banner de pausa ACTIVA: full-width, bien visible, con timer y reanudar. */}
      {activa && (
        <div
          role="status"
          aria-live="polite"
          className="fixed inset-x-0 top-0 z-[110] bg-primary text-on-primary shadow-lg animate-in fade-in"
        >
          <div className="max-w-5xl mx-auto flex items-center justify-between gap-md px-lg py-sm">
            <div className="flex items-center gap-sm">
              <Icon name="pause_circle" className="text-[24px]" fill />
              <div>
                <p className="font-bold text-label-md leading-tight">PAUSA AUTORIZADA en curso</p>
                <p className="text-label-sm opacity-90 leading-tight">
                  La supervisión sigue activa. El tiempo de pausa queda registrado.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-md">
              <span className="font-mono font-bold text-title-lg tabular-nums">{mmss(transcurrido)}</span>
              <Button
                variant="secondary"
                size="sm"
                icon="play_circle"
                onClick={() => void reanudar()}
                disabled={reanudando}
              >
                {reanudando ? 'Reanudando…' : 'Reanudar examen'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Modal simple para capturar el motivo de la pausa. */}
      {modalMotivo && (
        <div className="fixed inset-0 z-[95] bg-inverse-surface/60 backdrop-blur-sm flex items-center justify-center p-lg animate-in fade-in">
          <Card className="max-w-md w-full space-y-md">
            <div className="space-y-base">
              <h3 className="font-headline text-headline-md text-on-surface">Solicitar pausa</h3>
              <p className="text-label-sm text-on-surface-variant">
                Indicá brevemente el motivo. El proctor lo verá para decidir.
              </p>
            </div>
            <textarea
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              rows={3}
              autoFocus
              placeholder="Ej.: necesito ir al baño"
              className="w-full px-sm py-base text-label-md rounded-xl border border-outline-variant bg-surface-container-lowest focus:border-primary-container outline-none resize-none"
            />
            <div className="flex gap-base justify-end">
              <Button variant="outline" size="sm" onClick={() => setModalMotivo(false)} disabled={pidiendo}>
                Cancelar
              </Button>
              <Button
                size="sm"
                icon="send"
                onClick={() => void confirmarSolicitud()}
                disabled={!motivo.trim() || pidiendo}
              >
                {pidiendo ? 'Enviando…' : 'Enviar solicitud'}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}

export default PausaAlumno;
