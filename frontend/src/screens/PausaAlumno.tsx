/**
 * PausaAlumno — Flujo de pausa autorizada del lado del ESTUDIANTE (C-15).
 *
 * El alumno solicita una pausa (con motivo); el tutor la aprueba/rechaza desde
 * su panel. Esta UI pollea `listarPausas(sessionId)` y refleja el estado de la
 * pausa más reciente:
 *   - solicitada → "Esperando aprobación del tutor…"
 *   - aprobada   → banner de PAUSA ACTIVA bien visible + timer + "Reanudar examen"
 *   - rechazada  → aviso EN PANTALLA, persistente (Card visible con el motivo del
 *                  tutor), hasta que el alumno lo cierre o pida otra pausa
 *   - finalizada → estado normal
 *
 * IMPORTANTE (decisión de producto, Opción 1): la detección NO se apaga durante
 * la pausa. El cliente sigue siendo sensor; el backend contextualiza los eventos
 * (flag en_pausa_autorizada) y los excluye del score. Este componente solo toca UI.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Card, Button, Icon } from '../ui/components';
import { useToast } from '../ui/toast';
import { api } from '../lib/api';
import { getEffectiveConfig } from '../config/effectiveConfigCache';
import { intervaloDePolling } from './pausaCadencia';
import type { Pausa } from '../lib/types';

// La cadencia del poller es ADAPTATIVA (c-78): rápida solo cuando hay algo en
// vuelo. Ver `pausaCadencia.ts` para el porqué y los números medidos.

/** Formatea segundos transcurridos como mm:ss. */
function mmss(totalSeg: number): string {
  const s = Math.max(0, Math.floor(totalSeg));
  const mm = String(Math.floor(s / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

export function PausaAlumno({
  sessionId,
  onActivaChange,
}: {
  sessionId: string | null | undefined;
  /** Notifica al contenedor cuándo la pausa está ACTIVA, para que empuje el layout
   *  (padding-top) y el banner full-width no tape el header/controles del examen. */
  onActivaChange?: (activa: boolean) => void;
}) {
  const toast = useToast();
  const [pausa, setPausa] = useState<Pausa | null>(null);
  const [pidiendo, setPidiendo] = useState(false);
  const [reanudando, setReanudando] = useState(false);
  const [transcurrido, setTranscurrido] = useState(0);
  const [modalMotivo, setModalMotivo] = useState(false);
  const [motivo, setMotivo] = useState('');
  // Id de la pausa rechazada cuyo aviso EN PANTALLA el alumno ya cerró (para no
  // re-mostrarlo en cada poll). El aviso vive hasta que lo cierre o pida otra pausa.
  const [rechazoCerrado, setRechazoCerrado] = useState<string | null>(null);

  const enVuelo = useRef(false);

  const refrescar = useCallback(async () => {
    if (!sessionId || enVuelo.current) return;
    enVuelo.current = true;
    try {
      const lista = await api.listarPausas(sessionId);
      // La más reciente es la primera (el backend ordena desc por solicitada_en).
      const actual = lista[0] ?? null;
      setPausa(actual);
    } catch {
      // Degradación silenciosa.
    } finally {
      enVuelo.current = false;
    }
  }, [sessionId]);

  // Polling con cleanup. El intervalo depende del estado de la pausa: 3,5 s
  // mientras hay algo esperando resolución, 20 s cuando no hay nada.
  //
  // El cambio a rápido es INMEDIATO al pedir la pausa: `solicitarPausa` hace
  // `setPausa()` con la respuesta del POST, así que este effect se re-ejecuta con
  // el estado nuevo en el mismo render. El alumno no espera ni un segundo más que
  // antes — lo único que cambia es que deja de preguntar al vacío las dos horas
  // que NO está pidiendo nada.
  const intervaloMs = intervaloDePolling(pausa?.estado);
  useEffect(() => {
    if (!sessionId) return;
    void refrescar();
    const id = setInterval(() => void refrescar(), intervaloMs);
    return () => clearInterval(id);
  }, [sessionId, refrescar, intervaloMs]);

  // Timer de la pausa activa: cuenta desde inicio_en (fuente: backend).
  const activa = pausa?.estado === 'aprobada';
  const inicioEn = pausa?.inicio_en ?? null;

  // Avisar al contenedor (Examen) cuándo hay pausa activa, para que empuje el
  // contenido y el banner full-width no tape los controles del examen.
  useEffect(() => {
    onActivaChange?.(activa);
  }, [activa, onActivaChange]);
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
    // Sin sesión de supervisión no se puede pedir pausa: avisamos en vez de abrir un
    // modal cuyo botón fallaría en silencio (síntoma "no deja solicitar pausas").
    if (!sessionId) {
      toast.info('Esperá a que inicie la supervisión para poder pedir una pausa.');
      return;
    }
    setMotivo('');
    // Al pedir otra pausa, dejamos de mostrar el aviso del rechazo anterior.
    if (pausa?.estado === 'rechazada') setRechazoCerrado(pausa.id);
    setModalMotivo(true);
  };

  const confirmarSolicitud = async () => {
    const m = motivo.trim();
    if (!m || pidiendo) return;
    if (!sessionId) {
      toast.error('No se pudo solicitar la pausa: la supervisión todavía no inició.');
      return;
    }
    setPidiendo(true);
    try {
      const p = await api.solicitarPausa(sessionId, m);
      setPausa(p);
      setModalMotivo(false);
      toast.info('Solicitud de pausa enviada al tutor');
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

  // C-69: límite de duración de la pausa. Al vencer, se reanuda sola (evita usar la
  // pausa para hacer tiempo / copiarse). El límite viene de la config del sistema.
  const pausaMaxMin = getEffectiveConfig()?.pausa_max_min ?? 10;
  const pausaMaxSeg = pausaMaxMin * 60;
  const restanteSeg = Math.max(0, Math.ceil(pausaMaxSeg - transcurrido));
  useEffect(() => {
    if (activa && transcurrido >= pausaMaxSeg && !reanudando) {
      toast.info('Se alcanzó el límite de la pausa. El examen se reanuda automáticamente.');
      void reanudar();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activa, transcurrido, pausaMaxSeg]);

  const estado = pausa?.estado;
  const esperando = estado === 'solicitada';
  // Mostramos el aviso de rechazo EN PANTALLA mientras la pausa más reciente esté
  // 'rechazada' y el alumno no lo haya cerrado. Persiste entre polls (no es un toast).
  const mostrarRechazo = estado === 'rechazada' && pausa != null && rechazoCerrado !== pausa.id;

  return (
    <>
      <Card className="space-y-sm">
        <h3 className="text-label-md font-bold text-on-surface border-b border-outline-variant/40 pb-base">
          Pausa autorizada
        </h3>

        {esperando ? (
          <div className="flex items-center gap-sm text-on-surface-variant py-base">
            <Icon name="progress_activity" className="text-[20px] text-warning ae-spin" />
            <p className="text-label-sm">Esperando aprobación del tutor…</p>
          </div>
        ) : activa ? (
          <p className="text-label-sm text-on-surface-variant">
            Tenés una pausa autorizada en curso. Reanudá el examen cuando estés listo/a.
          </p>
        ) : (
          <>
            {mostrarRechazo && pausa && (
              <div
                role="alert"
                className="rounded-xl border border-error/40 bg-error-container/60 px-sm py-base space-y-base"
              >
                <div className="flex items-start gap-sm">
                  <Icon name="cancel" className="text-[20px] text-error shrink-0 mt-px" fill />
                  <div className="min-w-0 flex-1 space-y-base">
                    <p className="text-label-md font-bold text-on-error-container">
                      El tutor rechazó tu pedido de pausa
                    </p>
                    {pausa.motivo_rechazo?.trim() ? (
                      <p className="text-label-sm text-on-error-container">
                        <span className="font-semibold">Motivo: </span>
                        {pausa.motivo_rechazo}
                      </p>
                    ) : (
                      <p className="text-label-sm text-on-error-container">
                        El tutor no indicó un motivo.
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    aria-label="Cerrar aviso"
                    onClick={() => setRechazoCerrado(pausa.id)}
                    className="shrink-0 text-on-error-container/70 hover:text-on-error-container"
                  >
                    <Icon name="close" className="text-[18px]" />
                  </button>
                </div>
              </div>
            )}
            <p className="text-label-sm text-on-surface-variant">
              Si necesitás interrumpir el examen (ir al baño, una urgencia), pedí una pausa.
              El tutor la aprueba; durante la pausa la supervisión sigue activa.
            </p>
            <Button variant="secondary" size="sm" onClick={abrirSolicitud} disabled={!sessionId}>
              Solicitar pausa
            </Button>
            {!sessionId && (
              <p className="text-label-sm text-on-surface-variant/70">
                Disponible cuando inicie la supervisión.
              </p>
            )}
          </>
        )}
      </Card>

      {/* Pausa ACTIVA: overlay BLOQUEANTE que TAPA todo el examen hasta reanudar.
          z-[100] (igual que el monitor bloqueante): el alumno no ve ni interactúa
          con las preguntas mientras está en pausa (no puede espiar el examen). */}
      {activa && createPortal(
        <div
          role="alertdialog"
          aria-modal="true"
          aria-live="polite"
          aria-label="Pausa autorizada en curso"
          className="fixed inset-0 z-[100] bg-inverse-surface/90 backdrop-blur-md flex items-center justify-center p-lg animate-in fade-in"
        >
          <Card className="max-w-lg w-full text-center space-y-lg">
            <div className="w-20 h-20 rounded-full bg-primary-container text-primary flex items-center justify-center mx-auto">
              <Icon name="pause_circle" className="text-[44px]" fill />
            </div>
            <div className="space-y-base">
              <h2 className="font-headline text-headline-md text-on-surface">Pausa autorizada en curso</h2>
              <p className="text-body-md text-on-surface-variant">
                El examen está en pausa. Reanudalo cuando estés listo/a para seguir.
              </p>
            </div>
            <div className="font-mono font-bold text-display-sm text-on-surface tabular-nums">
              {mmss(transcurrido)}
            </div>
            <p className="text-label-md text-warning font-medium">
              Se reanuda sola en {mmss(restanteSeg)} (máximo {pausaMaxMin} min de pausa).
            </p>
            <p className="text-label-sm text-on-surface-variant">
              La supervisión sigue activa y el tiempo de pausa queda registrado.
            </p>
            <Button
              icon="play_circle"
              onClick={() => void reanudar()}
              disabled={reanudando}
              className="w-full"
            >
              {reanudando ? 'Reanudando…' : 'Reanudar examen'}
            </Button>
          </Card>
        </div>,
        document.body,
      )}

      {/* Modal para capturar el motivo. Portalizado a <body> para escapar cualquier
          ancestro con transform (el `animate-in` del examen contendría el `fixed` y
          dejaría una franja sin cubrir arriba). */}
      {modalMotivo && createPortal(
        <div className="fixed inset-0 z-[95] bg-inverse-surface/80 flex items-center justify-center p-lg animate-in fade-in">
          <Card className="max-w-md w-full space-y-md">
            <div className="space-y-base">
              <h3 className="font-headline text-headline-md text-on-surface">Solicitar pausa</h3>
              <p className="text-label-sm text-on-surface-variant">
                Indicá brevemente el motivo. El tutor lo verá para decidir.
              </p>
            </div>
            <textarea
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              rows={3}
              autoFocus
              placeholder="Ej.: necesito ir al baño"
              className="w-full px-4 py-3 text-label-md rounded-lg border border-outline-variant bg-surface-container-lowest focus:border-primary-container outline-none resize-none"
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
        </div>,
        document.body,
      )}
    </>
  );
}

export default PausaAlumno;
