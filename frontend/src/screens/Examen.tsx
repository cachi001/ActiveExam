import { useEffect, useMemo, useRef, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { useExamProctoring } from '../proctoring/useExamProctoring';
import { getEffectiveConfig, loadEffectiveConfig } from '../config/effectiveConfigCache';
import type { EventoSesion } from '../lib/types';
import { fetchExamenParaRendir } from '../lib/examTakingApi';
import type { ExamenRendicion } from '../lib/examTakingApi';
import {
  avanzarPregunta,
  retrocederPregunta,
  preguntaEnIndice,
  indicesRespondidos,
  mezclarConSemilla,
} from './ExamenLogic';
import { FullscreenLockdown } from '../proctoring/fullscreenLockdown';
import { MonitorBloqueante } from './examen/MonitorBloqueante';
import { AlertaCritica } from './examen/AlertaCritica';
import { LockdownOverlay } from './examen/LockdownOverlay';
import { ExamenPreguntaCard } from './examen/ExamenPreguntaCard';
import { ExamenErrorInicio } from './examen/ExamenErrorInicio';
import { ExamenCamaraPanel } from './examen/ExamenCamaraPanel';
import { IntegridadPanel } from './examen/IntegridadPanel';
import { QuestionNavigator } from './alumno/components/QuestionNavigator';
import { PausaAlumno } from './PausaAlumno';
import { ChatBox } from '../ui/ChatBox';
import { Card, Button } from '../ui/components';

export default function Examen() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [tiempoLimiteMin, setTiempoLimiteMin] = useState<number | null | undefined>(undefined);
  const [segRestantes, setSegRestantes] = useState<number | null>(null);
  const [alerta, setAlerta] = useState<EventoSesion | null>(null);
  const [pausaActiva, setPausaActiva] = useState(false);

  const [preguntasRaw, setPreguntasRaw] = useState<ExamenRendicion['preguntas']>([]);
  const [mezclar, setMezclar] = useState(false);
  const [cargandoPreguntas, setCargandoPreguntas] = useState(false);
  const entregadoRef = useRef(false);
  const [indiceActual, setIndiceActual] = useState(0);
  const [respuestas, setRespuestas] = useState<Record<string, string>>({});

  const [bloqueado, setBloqueado] = useState(false);
  const lockdownRef = useRef<FullscreenLockdown | null>(null);

  const [chatHabilitado, setChatHabilitado] = useState(true);
  const [pausasHabilitadas, setPausasHabilitadas] = useState(true);
  useEffect(() => {
    void loadEffectiveConfig().then(() => {
      const cfg = getEffectiveConfig();
      if (cfg) {
        setChatHabilitado(cfg.chat_habilitado);
        setPausasHabilitadas(cfg.pausas_habilitadas);
      }
    });
  }, []);

  const { sessionId, score, eventCount, activo, eventos, extraMonitorActive, sessionError, detener } = useExamProctoring(videoRef, examen);

  // Entrega: confirmación previa (nunca finalizar por un click accidental) + estado
  // de envío + error de entrega (si el POST de respuestas falla NO se navega a /cierre,
  // así no le "terminamos" el examen al alumno sin haber guardado nada).
  const [confirmandoEntrega, setConfirmandoEntrega] = useState(false);
  const [entregando, setEntregando] = useState(false);
  const [errorEntrega, setErrorEntrega] = useState(false);

  useEffect(() => {
    navigator.mediaDevices?.getUserMedia({ video: true }).then((s) => {
      streamRef.current = s;
      if (videoRef.current) { videoRef.current.srcObject = s; videoRef.current.play().catch(() => {}); }
    }).catch(() => {});
    return () => streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  useEffect(() => {
    const t = setInterval(
      () => setSegRestantes((s) => (s === null ? null : s <= 0 ? 0 : s - 1)),
      1000,
    );
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const examenContenidoId = examen?.examen_contenido_id;
    if (!examenContenidoId) return;
    setCargandoPreguntas(true);
    fetchExamenParaRendir(examenContenidoId)
      .then((data) => {
        if (!data) return;
        setPreguntasRaw(data.preguntas);
        setMezclar(!!data.mezclar_preguntas);
        const tl = data.tiempo_limite_min ?? null;
        setTiempoLimiteMin(tl);
        setSegRestantes(tl !== null && tl > 0 ? tl * 60 : null);
      })
      .catch(() => {})
      .finally(() => setCargandoPreguntas(false));
  }, [examen?.examen_contenido_id]);

  const lastAlertaId = useRef<string | null>(null);
  useEffect(() => {
    const critico = eventos.find(
      (e) => (e.severidad === 'alta' || e.severidad === 'critica') && e.tipo !== 'monitor_adicional',
    );
    if (critico && critico.id !== lastAlertaId.current) {
      lastAlertaId.current = critico.id;
      setAlerta(critico);
    }
  }, [eventos]);

  useEffect(() => {
    const lockdown = new FullscreenLockdown(
      (state) => setBloqueado(state.bloqueado),
      (_tipo) => {},
    );
    lockdownRef.current = lockdown;
    lockdown.iniciar().catch(() => {});
    return () => lockdown.detener();
  }, []);

  /**
   * Entrega el intento: envía las respuestas server-side (para calcular la nota) y
   * finaliza la sesión, luego navega a /cierre.
   *
   * `porTiempo=false` (entrega manual): si el POST de respuestas FALLA, NO se navega
   * a /cierre — se libera el guard y se muestra el error para que el alumno reintente.
   * Terminarle el examen sin haber guardado nada sería el peor resultado posible.
   *
   * `porTiempo=true` (tiempo agotado): no podemos retener al alumno pasado el límite,
   * así que se navega a /cierre aunque el POST falle (best-effort).
   */
  const entregar = async (porTiempo = false) => {
    if (entregadoRef.current) return;
    entregadoRef.current = true;
    setEntregando(true);
    setErrorEntrega(false);
    try {
      if (sessionId) {
        const items = Object.entries(respuestas).map(([pregunta_id, opcion_elegida_id]) => ({
          pregunta_id,
          opcion_elegida_id,
        }));
        await api.enviarRespuestasProctoring(sessionId, items);
      }
    } catch {
      if (!porTiempo) {
        // Entrega manual fallida: revertir para permitir reintento. No finalizamos.
        entregadoRef.current = false;
        setEntregando(false);
        setErrorEntrega(true);
        return;
      }
      // Por tiempo: seguimos a /cierre igual (degradación best-effort).
    }
    setConfirmandoEntrega(false);
    detener();
    navigate('/cierre');
  };

  useEffect(() => {
    if (segRestantes === 0 && typeof tiempoLimiteMin === 'number' && tiempoLimiteMin > 0) {
      void entregar(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segRestantes, tiempoLimiteMin]);

  const seedMezcla = sessionId ?? examen?.examen_contenido_id ?? examen?.id ?? 'sin-sesion';
  const preguntas = useMemo(
    () => (mezclar ? mezclarConSemilla(preguntasRaw, seedMezcla) : preguntasRaw),
    [preguntasRaw, mezclar, seedMezcla],
  );

  const total = preguntas.length;
  const preguntaActual = preguntaEnIndice(preguntas, indiceActual);
  const respondidas = indicesRespondidos(preguntas, respuestas);
  const sinResponder = total - respondidas.size;

  // No se pudo iniciar la sesión (intentos agotados, fuera de ventana, red): bloqueamos
  // la entrada. Rendir sin sesión es imposible de forma segura — las respuestas no se
  // guardarían ni se calcularía la nota. Antes el alumno entraba a un examen fantasma.
  if (sessionError) {
    return (
      <StudentShell locked>
        <ExamenErrorInicio error={sessionError} onVolver={() => navigate('/alumno/mis-examenes')} />
      </StudentShell>
    );
  }

  return (
    <StudentShell locked>
      <div className={`w-full animate-in fade-in duration-500 transition-[padding] ${pausaActiva ? 'pt-16' : ''}`}>

        {/* Preguntas (izquierda) + rail derecho: cámara arriba, luego números +
            Terminar intento, y abajo Supervisión. */}
        <div className="flex flex-col lg:flex-row gap-lg items-start">
          <main className="flex-1 min-w-0 w-full space-y-lg">
            <ExamenPreguntaCard
              preguntaActual={preguntaActual}
              indiceActual={indiceActual}
              total={total}
              cargandoPreguntas={cargandoPreguntas}
              respuestas={respuestas}
              respondidas={respondidas}
              segRestantes={segRestantes}
              tiempoLimiteMin={tiempoLimiteMin}
              onSeleccionarOpcion={(pid, oid) => setRespuestas((prev) => ({ ...prev, [pid]: oid }))}
              onAnterior={() => setIndiceActual((i) => retrocederPregunta(i))}
              onSiguiente={() => setIndiceActual((i) => avanzarPregunta(i, total))}
            />

            {/* Canal del proctor + supervisión en vivo. Si el chat está apagado, la
                supervisión ocupa todo el ancho (sin hueco). */}
            <div className={`grid gap-md items-start ${chatHabilitado ? 'md:grid-cols-2' : 'grid-cols-1'}`}>
              {chatHabilitado && (
                <ChatBox sessionId={sessionId} yo="alumno" titulo="Canal con el proctor" altura="h-[160px]" />
              )}
              <IntegridadPanel
                activo={activo}
                eventCount={eventCount}
                score={score}
                eventos={eventos}
                examen={examen}
              />
            </div>
          </main>

          <aside className="w-full lg:w-[400px] shrink-0 lg:sticky lg:top-6 space-y-md">
            {/* Cámara — arriba a la derecha */}
            <ExamenCamaraPanel videoRef={videoRef} />

            {/* Números de preguntas + Terminar intento */}
            {total > 0 && (
              <Card className="space-y-md">
                <h3 className="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wide">
                  Preguntas
                </h3>
                <QuestionNavigator
                  total={total}
                  indiceActual={indiceActual}
                  respondidas={respondidas}
                  onIr={setIndiceActual}
                />
                <Button
                  variant="secondary"
                  onClick={() => { setErrorEntrega(false); setConfirmandoEntrega(true); }}
                  className="w-full mt-base"
                >
                  Terminar intento
                </Button>
              </Card>
            )}

            {/* Pausa autorizada */}
            {pausasHabilitadas && (
              <PausaAlumno sessionId={sessionId} onActivaChange={setPausaActiva} />
            )}
          </aside>
        </div>
      </div>

      {confirmandoEntrega && (
        <div
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="confirmar-entrega-titulo"
          className="fixed inset-0 z-[95] bg-inverse-surface/80 backdrop-blur-md flex items-center justify-center p-lg animate-in fade-in"
        >
          <Card className="max-w-md w-full space-y-md">
            <div className="space-y-base">
              <h3 id="confirmar-entrega-titulo" className="font-headline text-headline-md text-on-surface">
                ¿Entregar el examen?
              </h3>
              <p className="text-body-md text-on-surface-variant">
                Respondiste <strong>{respondidas.size} de {total}</strong> preguntas.
                {sinResponder > 0 && (
                  <> Te {sinResponder === 1 ? 'queda' : 'quedan'} <strong>{sinResponder} sin responder</strong>.</>
                )}
              </p>
              <p className="text-label-sm text-on-surface-variant">
                Una vez que entregás <strong>no vas a poder volver a cambiar tus respuestas</strong>.
              </p>
              {errorEntrega && (
                <div role="alert" className="rounded-xl border border-error/40 bg-error-container/60 px-sm py-base text-label-sm text-on-error-container">
                  No pudimos entregar tu examen. Revisá tu conexión e intentá de nuevo — tus
                  respuestas siguen acá, no se perdió nada.
                </div>
              )}
            </div>
            <div className="flex gap-base justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmandoEntrega(false)}
                disabled={entregando}
              >
                Seguir en el examen
              </Button>
              <Button
                size="sm"
                icon={entregando ? undefined : 'check'}
                onClick={() => void entregar(false)}
                disabled={entregando}
              >
                {entregando ? 'Entregando…' : 'Sí, entregar'}
              </Button>
            </div>
          </Card>
        </div>
      )}

      {alerta && <AlertaCritica ev={alerta} onClose={() => setAlerta(null)} />}
      {extraMonitorActive && <MonitorBloqueante />}
      {bloqueado && (
        <LockdownOverlay onVolverAPantallaCompleta={() => lockdownRef.current?.volverAPantallaCompleta()} />
      )}
    </StudentShell>
  );
}
