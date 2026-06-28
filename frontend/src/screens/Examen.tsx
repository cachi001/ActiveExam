import { useEffect, useRef, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card, SeverityBadge } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { TIPO_EVENTO_LABEL } from '../lib/api';
import { useExamProctoring } from '../proctoring/useExamProctoring';
import { pesoEvento } from '../proctoring/scoringWeights';
import { getEffectiveConfig } from '../config/effectiveConfigCache';
import { ChatBox } from '../ui/ChatBox';
import { PausaAlumno } from './PausaAlumno';
import type { EventoSesion, Severidad } from '../lib/types';
import { fetchExamenParaRendir } from '../lib/examTakingApi';
import type { ExamenRendicion } from '../lib/examTakingApi';
import {
  puedeIrAnterior,
  puedeIrSiguiente,
  avanzarPregunta,
  retrocederPregunta,
  preguntaEnIndice,
} from './ExamenLogic';
import { FullscreenLockdown, soportaFullscreen, MENSAJE_LIMITE_FULLSCREEN } from '../proctoring/fullscreenLockdown';

// Color de la card del evento según el riesgo/severidad (mismo código de color que
// la severidad: rojo = alto/crítico, ámbar = medio, azul = bajo).
const SEV_CARD: Record<string, string> = {
  critica: 'bg-error-container border-error/40',
  alta: 'bg-error-container border-error/40',
  media: 'bg-warning-container border-warning-200',
  baja: 'bg-blue-50 border-blue-200',
};
const SEV_ICON: Record<string, { name: string; cls: string }> = {
  critica: { name: 'gpp_bad', cls: 'text-error' },
  alta: { name: 'gpp_bad', cls: 'text-error' },
  media: { name: 'warning', cls: 'text-warning' },
  baja: { name: 'info', cls: 'text-blue-600' },
};

export default function Examen() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [segRestantes, setSegRestantes] = useState((examen?.duracion_min ?? 60) * 60);
  const [alerta, setAlerta] = useState<EventoSesion | null>(null);
  // C-15: cuando hay una pausa autorizada ACTIVA, PausaAlumno muestra un banner
  // fijo full-width debajo del topbar.
  const [pausaActiva, setPausaActiva] = useState(false);

  // C-69: preguntas de la API de rendición (sin es_correcta — D3)
  const [preguntas, setPreguntas] = useState<ExamenRendicion['preguntas']>([]);
  const [cargandoPreguntas, setCargandoPreguntas] = useState(false);
  // Índice de la pregunta actual en la navegación prev/next
  const [indiceActual, setIndiceActual] = useState(0);
  // Mapa de respuestas: preguntaId -> opcionId seleccionada
  const [respuestas, setRespuestas] = useState<Record<string, string>>({});

  // C-69 Section 5: estado de lockdown de pantalla completa
  const [bloqueado, setBloqueado] = useState(false);
  const lockdownRef = useRef<FullscreenLockdown | null>(null);

  // Proctoring REAL de fondo: motor MediaPipe + detectores de contexto + streaming
  // al backend (sesión modo:'examen'). Expone score/eventos/eventCount y detener().
  // sessionId alimenta el chat y el flujo de pausa autorizada (C-15).
  const { sessionId, score, eventCount, activo, eventos, extraMonitorActive, detener } = useExamProctoring(videoRef, examen);

  // cámara (preview en línea; el hook de proctoring consume este mismo <video>)
  useEffect(() => {
    navigator.mediaDevices?.getUserMedia({ video: true }).then((s) => {
      streamRef.current = s;
      if (videoRef.current) { videoRef.current.srcObject = s; videoRef.current.play().catch(() => {}); }
    }).catch(() => {});
    return () => streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  // temporizador
  useEffect(() => {
    const t = setInterval(() => setSegRestantes((s) => (s <= 0 ? 0 : s - 1)), 1000);
    return () => clearInterval(t);
  }, []);

  // C-69: cargar preguntas de la API de rendición al montar
  useEffect(() => {
    const examenContenidoId = examen?.examen_contenido_id;
    if (!examenContenidoId) return;
    setCargandoPreguntas(true);
    fetchExamenParaRendir(examenContenidoId)
      .then((data) => {
        if (data) {
          setPreguntas(data.preguntas);
        }
      })
      .catch(() => {
        // Error de red: el examen sigue funcionando (degradación silenciosa)
      })
      .finally(() => setCargandoPreguntas(false));
  }, [examen?.examen_contenido_id]);

  // Alerta sobria ante eventos de alta/crítica detectados realmente.
  // Nota: ignora monitor_adicional aquí; la incidencia de monitor se maneja con un
  // modal bloqueante dedicado (ver MonitorBloqueante más abajo) que no se cierra hasta
  // que el monitor extra se desconecte.
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

  // C-69 Section 5: inicializar el lockdown al iniciar el examen
  // El lockdown se crea cuando el componente monta y se detiene al desmontar.
  // L2.5: bloquea y re-fuerza, NUNCA expulsa ni anula la sesión.
  useEffect(() => {
    const lockdown = new FullscreenLockdown(
      (state) => setBloqueado(state.bloqueado),
      // onSenalParaScore: las señales de fullscreen/blur siguen al pipeline de score
      // via useExamProctoring (D4: retrocompat intacta). No hacemos nada extra aquí.
      (_tipo) => {},
    );
    lockdownRef.current = lockdown;
    // Iniciar en respuesta al mount (el alumno ya hizo clic para llegar aquí)
    lockdown.iniciar().catch(() => {});
    return () => lockdown.detener();
  }, []);

  // Cierre prolijo: cortar el proctoring antes de navegar (eventos ya persistidos).
  const finalizar = () => {
    detener();
    navigate('/cierre');
  };

  const mm = String(Math.floor(segRestantes / 60)).padStart(2, '0');
  const ss = String(segRestantes % 60).padStart(2, '0');

  // C-69: pregunta actual y estado de navegación
  const total = preguntas.length;
  const preguntaActual = preguntaEnIndice(preguntas, indiceActual);

  const handleSeleccionarOpcion = (preguntaId: string, opcionId: string) => {
    setRespuestas((prev) => ({ ...prev, [preguntaId]: opcionId }));
  };

  const handleAnterior = () => setIndiceActual((i) => retrocederPregunta(i));
  const handleSiguiente = () => setIndiceActual((i) => avanzarPregunta(i, total));

  return (
    <StudentShell>
      <div
        className={`grid lg:grid-cols-3 gap-lg animate-in fade-in duration-500 transition-[padding] ${
          pausaActiva ? 'pt-16' : ''
        }`}
      >
        {/* Examen */}
        <div className="lg:col-span-2 space-y-lg">
          <Card className="space-y-md">
            <div className="flex items-center justify-between border-b border-outline-variant/40 pb-md">
              <div>
                {preguntaActual && (
                  <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">
                    Pregunta {indiceActual + 1} de {total}
                  </p>
                )}
                {cargandoPreguntas && (
                  <p className="text-body-md text-on-surface-variant">Cargando preguntas…</p>
                )}
                {!cargandoPreguntas && !preguntaActual && (
                  <p className="text-body-md text-on-surface-variant">
                    No hay preguntas disponibles para este examen.
                  </p>
                )}
                {preguntaActual && (
                  <h2 className="font-headline text-title-lg text-on-surface mt-base">
                    {preguntaActual.enunciado}
                  </h2>
                )}
              </div>
              <span className={`inline-flex items-center gap-base px-sm py-base rounded-lg text-label-md font-bold ${segRestantes < 300 ? 'bg-error-container text-on-error-container' : 'bg-warning-container text-warning'}`}>
                <Icon name="timer" className="text-[18px]" /> {mm}:{ss}
              </span>
            </div>

            {preguntaActual && (
              <div className="space-y-sm">
                {preguntaActual.opciones.map((op) => {
                  const seleccionada = respuestas[preguntaActual.id] === op.id;
                  return (
                    <label key={op.id} className={`flex items-center gap-sm p-md rounded-xl border cursor-pointer transition-all ${
                      seleccionada
                        ? 'border-primary-container bg-primary-fixed/40'
                        : 'border-outline-variant hover:border-primary-container hover:bg-surface-container-low'
                    }`}>
                      <input
                        type="radio"
                        name={`q-${preguntaActual.id}`}
                        checked={seleccionada}
                        onChange={() => handleSeleccionarOpcion(preguntaActual.id, op.id)}
                        className="w-4 h-4 accent-[#4241bc]"
                      />
                      <span className="text-body-md text-on-surface">{op.texto}</span>
                    </label>
                  );
                })}
              </div>
            )}

            <div className="flex items-center justify-between pt-md border-t border-outline-variant/40 gap-sm">
              {puedeIrAnterior(indiceActual) ? (
                <Button icon="arrow_back" onClick={handleAnterior} className="sm:w-auto">
                  Anterior
                </Button>
              ) : (
                <div />
              )}
              {puedeIrSiguiente(indiceActual, total) ? (
                <Button icon="arrow_forward" onClick={handleSiguiente} className="sm:w-auto">
                  Siguiente
                </Button>
              ) : (
                <Button icon="check_circle" onClick={finalizar} className="sm:w-auto">
                  Finalizar y entregar
                </Button>
              )}
            </div>

            {/* DD-21/D6: límite honesto del lockdown — solo visible si el navegador
                no soporta la Fullscreen API o si el lockdown está activo */}
            {!soportaFullscreen() && (
              <p className="text-label-sm text-on-surface-variant mt-base italic">
                {MENSAJE_LIMITE_FULLSCREEN}
              </p>
            )}
          </Card>
        </div>

        {/* Panel de proctoring */}
        <div className="space-y-lg">
          <Card padded={false} className="overflow-hidden">
            <div className="relative aspect-video bg-inverse-surface">
              <video ref={videoRef} muted playsInline className="w-full h-full object-cover" style={{ transform: 'scaleX(-1)' }} />
              {/* La detección sigue corriendo en segundo plano (useExamProctoring);
                  no se dibuja ningún marco/overlay ni badge encima del video para no
                  tapar ni confundir. El estado va abajo, discreto. */}
              {/* Indicador discreto de supervisión real en vivo */}
              <div className="absolute bottom-3 left-3 inline-flex items-center gap-base bg-inverse-surface/70 text-inverse-on-surface text-[9px] font-semibold px-sm py-base rounded-full">
                <span className={`w-1.5 h-1.5 rounded-full ${activo ? 'bg-success animate-pulse' : 'bg-on-surface-variant'}`} />
                Supervisión activa · {eventCount} eventos
              </div>
            </div>
          </Card>

          <Card className="space-y-sm">
            <div className="border-b border-outline-variant/40 pb-md space-y-sm">
              <h3 className="text-label-md font-bold text-on-surface">Señales de integridad (en vivo)</h3>
              {(() => {
                const umbral = getEffectiveConfig()?.umbral_cola_revision ?? examen?.umbral_score ?? 70;
                const enRiesgo = score >= umbral;
                return (
                  <>
                    <div className="flex items-baseline gap-sm">
                      <span className={`text-[32px] font-bold leading-none ${enRiesgo ? 'text-error' : 'text-on-surface'}`}>
                        {score}
                      </span>
                      <span className="text-label-md text-on-surface-variant">pts de riesgo</span>
                    </div>
                    <p className={`text-label-sm ${enRiesgo ? 'text-error font-semibold' : 'text-on-surface-variant'}`}>
                      {enRiesgo
                        ? `Alcanzaste ${umbral} pts: tu sesión va a revisión de un docente.`
                        : `Desde ${umbral} puntos tu sesión pasa a revisión de un docente.`}
                    </p>
                  </>
                );
              })()}
            </div>
            <div className="space-y-base max-h-[220px] overflow-y-auto">
              {eventos.length === 0 ? (
                <div className="text-center py-lg text-on-surface-variant space-y-base">
                  <Icon name="check_circle" className="text-success text-[32px]" fill />
                  <p className="text-label-sm">Integridad óptima. Sin incidencias en el navegador.</p>
                </div>
              ) : eventos.map((ev) => {
                const card = SEV_CARD[ev.severidad] ?? SEV_CARD.baja;
                const ic = SEV_ICON[ev.severidad] ?? SEV_ICON.baja;
                const puntosEv = pesoEvento(ev.tipo, ev.severidad as Severidad);
                return (
                  <div key={ev.id} className={`flex gap-sm p-sm rounded-xl border ${card}`}>
                    <Icon name={ic.name} className={`${ic.cls} shrink-0 text-[18px]`} fill />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-base">
                        <span className="text-label-md font-semibold text-on-surface">{TIPO_EVENTO_LABEL[ev.tipo]}</span>
                        <div className="flex items-center gap-base shrink-0">
                          <span className="text-label-sm font-bold font-mono text-on-surface">+{puntosEv} pts</span>
                          <SeverityBadge severidad={ev.severidad} />
                        </div>
                      </div>
                      <p className="text-label-sm text-on-surface-variant mt-base">{ev.descripcion}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* C-15: flujo de pausa autorizada (solicitar / esperar / activa+timer). */}
          <PausaAlumno sessionId={sessionId} onActivaChange={setPausaActiva} />

          {/* C-15: canal de chat bidireccional con el proctor (poll incremental). */}
          <ChatBox sessionId={sessionId} yo="alumno" titulo="Canal con el proctor" altura="h-[140px]" />
        </div>
      </div>

      {alerta && <AlertaCritica ev={alerta} onClose={() => setAlerta(null)} />}
      {/* Modal BLOQUEANTE: aparece cuando hay monitor adicional detectado.
          No se puede cerrar mientras el monitor siga conectado.
          Se cierra automaticamente cuando el polling reporta extraMonitorActive=false. */}
      {extraMonitorActive && <MonitorBloqueante />}

      {/* C-69 Section 5: overlay de lockdown de pantalla completa.
          L2.5: bloquea e invita a volver, NUNCA expulsa ni anula la sesión.
          Aparece ante fullscreen_exited / blur / visibilitychange=hidden. */}
      {bloqueado && (
        <LockdownOverlay
          onVolverAPantallaCompleta={() => lockdownRef.current?.volverAPantallaCompleta()}
        />
      )}
    </StudentShell>
  );
}

function MonitorBloqueante() {
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="monitor-bloqueante-titulo"
      className="fixed inset-0 z-[100] bg-inverse-surface/80 backdrop-blur-md flex items-center justify-center p-lg animate-in fade-in"
    >
      <Card className="max-w-lg w-full text-center space-y-md border-error/40">
        <div className="w-16 h-16 rounded-full bg-error-container text-error flex items-center justify-center mx-auto">
          <Icon name="block" className="text-[36px]" fill />
        </div>
        <div className="space-y-base">
          <h3 id="monitor-bloqueante-titulo" className="font-headline text-headline-md text-on-surface">
            Pantalla adicional detectada
          </h3>
          <p className="text-body-md text-on-surface-variant">
            El examen requiere <strong>un único monitor</strong>. Detectamos que tenés más de una
            pantalla conectada al equipo.
          </p>
          <p className="text-label-sm text-on-surface-variant">
            Desconectá la pantalla adicional para volver a habilitar el examen. Esta ventana se
            cerrará automáticamente cuando solo quede un monitor.
          </p>
        </div>
        <div className="inline-flex items-center gap-base px-sm py-base rounded-lg bg-warning-container text-warning text-label-sm">
          <Icon name="info" className="text-[16px]" fill />
          <span>Mientras tanto, no podés interactuar con el examen.</span>
        </div>
      </Card>
    </div>
  );
}

function AlertaCritica({ ev, onClose }: { ev: EventoSesion; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[90] bg-inverse-surface/60 backdrop-blur-sm flex items-center justify-center p-lg animate-in fade-in">
      <Card className="max-w-md w-full text-center space-y-md border-error/30">
        <div className="w-16 h-16 rounded-full bg-error-container text-error flex items-center justify-center mx-auto">
          <Icon name="gpp_maybe" className="text-[36px]" fill />
        </div>
        <div className="space-y-base">
          <h3 className="font-headline text-headline-md text-on-surface">Atención: incidencia detectada</h3>
          <p className="text-body-md text-on-surface-variant">
            Se registró <strong>{TIPO_EVENTO_LABEL[ev.tipo]}</strong>. {ev.descripcion}
          </p>
          <p className="text-label-sm text-on-surface-variant">
            Esto quedó registrado como señal (no es una sanción). Corregí la situación para continuar con normalidad.
          </p>
        </div>
        <Button icon="check" onClick={onClose} className="mx-auto">Entendido, continuar</Button>
      </Card>
    </div>
  );
}

/**
 * C-69 Section 5: overlay de bloqueo de pantalla completa.
 * L2.5: invita a volver — NUNCA expulsa ni anula la sesión automáticamente.
 * DD-21/D6: el navegador detecta y reacciona; no puede impedir el minimize del SO.
 */
function LockdownOverlay({ onVolverAPantallaCompleta }: { onVolverAPantallaCompleta: () => void }) {
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="lockdown-overlay-titulo"
      className="fixed inset-0 z-[95] bg-inverse-surface/90 backdrop-blur-md flex items-center justify-center p-lg animate-in fade-in"
    >
      <Card className="max-w-lg w-full text-center space-y-md border-warning/40">
        <div className="w-16 h-16 rounded-full bg-warning-container text-warning flex items-center justify-center mx-auto">
          <Icon name="fullscreen_exit" className="text-[36px]" fill />
        </div>
        <div className="space-y-base">
          <h3 id="lockdown-overlay-titulo" className="font-headline text-headline-md text-on-surface">
            Volvé a pantalla completa para continuar
          </h3>
          <p className="text-body-md text-on-surface-variant">
            El examen requiere pantalla completa. Saliste del modo pantalla completa,
            perdiste el foco o cambiaste de pestaña.
          </p>
          <p className="text-label-sm text-on-surface-variant">
            Esta salida quedó registrada como señal de supervisión (no es una sanción).
            Volvé a pantalla completa para seguir respondiendo.
          </p>
          <p className="text-label-xs text-on-surface-variant italic">
            {MENSAJE_LIMITE_FULLSCREEN}
          </p>
        </div>
        <Button
          icon="fullscreen"
          onClick={onVolverAPantallaCompleta}
          className="mx-auto"
        >
          Volver a pantalla completa
        </Button>
      </Card>
    </div>
  );
}
