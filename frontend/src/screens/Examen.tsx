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
import type { RespuestaEnvio } from '../lib/apiProctoring/respuestas';
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
import { Card, Button, Icon } from '../ui/components';

// C-72 sección 7: mensajes al alumno cuando el backend rechaza guardar respuestas
// (409). Distintos entre sí; alineados con Moodle (auto-entrega + aviso claro).
const MENSAJE_409: Record<string, string> = {
  tiempo_agotado:
    'Se agotó el tiempo del examen. Ya no se pueden guardar respuestas. Se conservaron las que enviaste dentro del plazo.',
  sesion_finalizada: 'Este examen ya fue entregado. No se puede modificar.',
};

function codigo409(e: unknown): string | undefined {
  const code = (e as { code?: string } | null)?.code;
  return code === 'tiempo_agotado' || code === 'sesion_finalizada' ? code : undefined;
}

/** Arma los items a enviar a POST /respuestas: multichoice + cloze (C-74 §6). */
function construirItemsRespuestas(
  respuestas: Record<string, string>,
  respuestasCloze: Record<string, Record<string, string>>,
): RespuestaEnvio[] {
  return [
    ...Object.entries(respuestas).map(
      ([pregunta_id, opcion_elegida_id]): RespuestaEnvio => ({ pregunta_id, opcion_elegida_id }),
    ),
    ...Object.entries(respuestasCloze)
      .filter(([, blanks]) => Object.keys(blanks).length > 0)
      .map(([pregunta_id, blanks]): RespuestaEnvio => ({ pregunta_id, respuesta_cloze: blanks })),
  ];
}

export default function Examen() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [tiempoLimiteMin, setTiempoLimiteMin] = useState<number | null | undefined>(undefined);
  // Ancla server-autoritativa del countdown: cuándo el alumno EMPEZÓ a rendir
  // (server la setea idempotente en el primer fetch). Preferida sobre creada_en de
  // la sesión, que puede caer en el consentimiento anticipado (fix del "60 → 58").
  const [examenIniciadoEn, setExamenIniciadoEn] = useState<string | null>(null);
  const [segRestantes, setSegRestantes] = useState<number | null>(null);
  const [alerta, setAlerta] = useState<EventoSesion | null>(null);
  const [pausaActiva, setPausaActiva] = useState(false);

  const [preguntasRaw, setPreguntasRaw] = useState<ExamenRendicion['preguntas']>([]);
  const [mezclar, setMezclar] = useState(false);
  const [cargandoPreguntas, setCargandoPreguntas] = useState(false);
  const entregadoRef = useRef(false);
  const [indiceActual, setIndiceActual] = useState(0);
  const [respuestas, setRespuestas] = useState<Record<string, string>>({});
  /** Respuestas cloze: preguntaId → { blankId → valor } */
  const [respuestasCloze, setRespuestasCloze] = useState<Record<string, Record<string, string>>>({});

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

  const { sessionId, sessionCreadaEn, score, eventCount, activo, eventos, extraMonitorActive, sessionError, detener } = useExamProctoring(videoRef, examen);

  // Entrega: confirmación previa (nunca finalizar por un click accidental) + estado
  // de envío + error de entrega (si el POST de respuestas falla NO se navega a /cierre,
  // así no le "terminamos" el examen al alumno sin haber guardado nada).
  const [confirmandoEntrega, setConfirmandoEntrega] = useState(false);
  const [entregando, setEntregando] = useState(false);
  const [errorEntrega, setErrorEntrega] = useState(false);
  // C-72 sección 7: mensaje de "se acabó el tiempo" / "ya finalizado" cuando el
  // backend rechaza guardar respuestas (409). NUNCA pérdida silenciosa.
  const [mensajeTiempo, setMensajeTiempo] = useState<string | null>(null);

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
        setTiempoLimiteMin(data.tiempo_limite_min ?? null);
        setExamenIniciadoEn(data.examen_iniciado_en ?? null);
        // segRestantes se calcula en el efecto de abajo, anclado al inicio REAL del
        // examen (examen_iniciado_en, server-autoritativo) — no acá, para no
        // regalarle tiempo extra a un F5.
      })
      .catch(() => {})
      .finally(() => setCargandoPreguntas(false));
  }, [examen?.examen_contenido_id]);

  // Vuln reload: ancla el countdown a un timestamp SERVER-AUTORITATIVO, NO a la hora
  // de montaje de este componente. Sin esto, recargar la página a mitad de examen le
  // regalaba `tiempo_limite_min` COMPLETOS de nuevo al alumno (timer reseteado).
  //
  // Ancla PREFERIDA: `examenIniciadoEn` (cuándo el alumno EMPEZÓ a rendir, seteado
  // por el server en el primer fetch). Fallback a `sessionCreadaEn` (creación de la
  // sesión) para backends viejos o sin sesión activa. Se prefiere `examenIniciadoEn`
  // porque la sesión puede crearse ANTES de rendir (consentimiento/biometría
  // anticipados) y anclar ahí le descontaría esos minutos al examen (bug "60 → 58").
  useEffect(() => {
    if (tiempoLimiteMin === null || tiempoLimiteMin === undefined || tiempoLimiteMin <= 0) {
      setSegRestantes(null);
      return;
    }
    const ancla = examenIniciadoEn ?? sessionCreadaEn;
    const anclaMs = ancla ? new Date(ancla).getTime() : Date.now();
    const transcurridoSeg = Math.floor((Date.now() - anclaMs) / 1000);
    const totalSeg = tiempoLimiteMin * 60;
    setSegRestantes(Math.max(0, totalSeg - transcurridoSeg));
  }, [tiempoLimiteMin, examenIniciadoEn, sessionCreadaEn]);

  const lastAlertaTsByTipo = useRef<Record<string, number>>({});
  const ALERTA_COOLDOWN_MS = 120_000;
  useEffect(() => {
    const critico = eventos.find(
      (e) => (e.severidad === 'alta' || e.severidad === 'critica') && e.tipo !== 'monitor_adicional',
    );
    if (!critico) return;
    const lastTs = lastAlertaTsByTipo.current[critico.tipo] ?? 0;
    if (Date.now() - lastTs < ALERTA_COOLDOWN_MS) return;
    lastAlertaTsByTipo.current[critico.tipo] = Date.now();
    setAlerta(critico);
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

  // Vuln reload — restauración: al reanudar una sesión (nueva o REANUDADA por el
  // backend idempotente tras un F5), traemos lo que el alumno ya había contestado
  // y lo mezclamos en `respuestas`. Sin esto, un F5 devolvía la misma sesión pero
  // con el examen en blanco (las respuestas vivían solo en React state, perdidas
  // al recargar). `respuestasHidratadasRef` evita que el submit incremental de
  // abajo dispare un POST espurio ANTES de que esta restauración termine.
  const respuestasHidratadasRef = useRef(false);
  useEffect(() => {
    if (!sessionId) return;
    respuestasHidratadasRef.current = false;
    (async () => {
      try {
        const guardadas = await api.obtenerRespuestasProctoring(sessionId);
        if (guardadas.length > 0) {
          const estandar: Record<string, string> = {};
          const cloze: Record<string, Record<string, string>> = {};
          for (const r of guardadas) {
            if (r.respuesta_cloze) {
              cloze[r.pregunta_id] = r.respuesta_cloze;
            } else if (r.opcion_elegida_id) {
              estandar[r.pregunta_id] = r.opcion_elegida_id;
            }
          }
          if (Object.keys(estandar).length > 0) {
            setRespuestas((prev) => ({ ...prev, ...estandar }));
          }
          if (Object.keys(cloze).length > 0) {
            setRespuestasCloze((prev) => ({ ...prev, ...cloze }));
          }
        }
      } catch {
        // Degradación silenciosa (R3): si falla, el alumno sigue con lo que tenga
        // en memoria — no bloquea el examen.
      } finally {
        respuestasHidratadasRef.current = true;
      }
    })();
  }, [sessionId]);

  // Vuln reload — submit incremental: guarda las respuestas server-side en CADA
  // cambio (debounced 800ms), no solo al entregar. Antes, `respuestas` vivía SOLO
  // en React state y se perdía por completo ante un F5 (o un cierre de pestaña).
  // Con esto, aunque el alumno recargue a mitad de examen, lo último que contestó
  // ya está persistido y se restaura por el efecto de arriba. Fire-and-forget
  // (degradación silenciosa): un fallo de red acá no debe romper el examen — la
  // entrega final (`entregar`) reintenta el POST completo igual.
  const submitTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!sessionId) return;
    if (!respuestasHidratadasRef.current) return; // aún restaurando: no pisar con {}
    if (submitTimeoutRef.current) clearTimeout(submitTimeoutRef.current);
    submitTimeoutRef.current = setTimeout(() => {
      const items = construirItemsRespuestas(respuestas, respuestasCloze);
      if (items.length === 0) return;
      // C-72 sección 7: si el backend rechaza por plazo (409), mostrar el aviso —
      // el alumno se entera de que se acabó el tiempo, sin pérdida silenciosa.
      api.enviarRespuestasProctoring(sessionId, items).catch((e) => {
        const code = codigo409(e);
        if (code) setMensajeTiempo(MENSAJE_409[code]);
      });
    }, 800);
    return () => {
      if (submitTimeoutRef.current) clearTimeout(submitTimeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [respuestas, respuestasCloze, sessionId]);

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
        const items = construirItemsRespuestas(respuestas, respuestasCloze);
        await api.enviarRespuestasProctoring(sessionId, items);
      }
    } catch (e) {
      const code = codigo409(e);
      if (code) {
        // C-72 sección 7: se acabó el tiempo o ya se entregó. Reintentar no sirve —
        // se muestra el aviso y se cierra (el backend ya finalizó la sesión).
        setMensajeTiempo(MENSAJE_409[code]);
      } else if (!porTiempo) {
        // Error de RED en entrega manual: revertir para permitir reintento. No finalizamos.
        entregadoRef.current = false;
        setEntregando(false);
        setErrorEntrega(true);
        return;
      }
      // 409 de plazo, o entrega por tiempo: seguimos a /cierre igual (best-effort).
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
  // Para el QuestionNavigator, unificamos respuestas estándar + cloze (al menos un blank)
  const respuestasCombinadas: Record<string, string> = {
    ...respuestas,
    ...Object.fromEntries(
      Object.entries(respuestasCloze)
        .filter(([, blanks]) => Object.values(blanks).some(Boolean))
        .map(([pid]) => [pid, '__cloze__']),
    ),
  };
  const respondidas = indicesRespondidos(preguntas, respuestasCombinadas);
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

        {/* C-72 sección 7: aviso de tiempo agotado / examen ya entregado. El backend
            rechazó guardar respuestas (409); el alumno se entera sin perder su trabajo. */}
        {mensajeTiempo && (
          <div
            role="alert"
            className="mb-lg rounded-xl border border-warning/50 bg-warning-container/70 px-md py-base
              text-label-md text-on-warning-container flex items-start gap-sm"
          >
            <Icon name="timer_off" className="text-[20px] shrink-0" fill />
            <span>{mensajeTiempo}</span>
          </div>
        )}

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
              respuestasCloze={respuestasCloze}
              respondidas={respondidas}
              segRestantes={segRestantes}
              tiempoLimiteMin={tiempoLimiteMin}
              onSeleccionarOpcion={(pid, oid) => setRespuestas((prev) => ({ ...prev, [pid]: oid }))}
              onRespuestaCloze={(pid, blankId, valor) =>
                setRespuestasCloze((prev) => ({
                  ...prev,
                  [pid]: { ...(prev[pid] ?? {}), [blankId]: valor },
                }))
              }
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
