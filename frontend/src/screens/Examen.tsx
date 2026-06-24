import { useEffect, useRef, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card, SeverityBadge } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { TIPO_EVENTO_LABEL, SEVERIDAD_LABEL } from '../lib/api';
import { useExamProctoring } from '../proctoring/useExamProctoring';
import { pesoEvento } from '../proctoring/scoringWeights';
import { getEffectiveConfig } from '../config/effectiveConfigCache';
import { useToast, type ToastTipo } from '../ui/toast';
import { ChatBox } from '../ui/ChatBox';
import { PausaAlumno } from './PausaAlumno';
import type { EventoSesion, Severidad } from '../lib/types';

// Severidad del evento -> tipo (y color) del toast de alerta en pantalla.
// baja=info(azul), media=warning(ámbar), alta/crítica=error(rojo) — mismo código
// de color que la card del evento y el SeverityBadge.
const SEV_TOAST: Record<string, ToastTipo> = {
  baja: 'info',
  media: 'warning',
  alta: 'error',
  critica: 'error',
};

const PREGUNTA = {
  numero: 'Pregunta 1 de 5',
  enunciado: '¿Cuál es la derivada de f(x) = x³ − 3x² + 2x respecto de x?',
  opciones: [
    "f '(x) = 3x² − 6x + 2",
    "f '(x) = x² − 3x + 2",
    "f '(x) = 3x² − 6x",
    "f '(x) = 3x³ − 6x² + 2x",
  ],
};

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
  const [opcion, setOpcion] = useState<number | null>(null);
  // C-15: cuando hay una pausa autorizada ACTIVA, PausaAlumno muestra un banner
  // fijo full-width debajo del topbar. Empujamos el contenido del examen hacia
  // abajo para que el banner no tape la pregunta ni los controles (bug z-index a
  // 1366px). El alto del banner (~60px) se compensa con padding-top en el grid.
  const [pausaActiva, setPausaActiva] = useState(false);

  // Proctoring REAL de fondo: motor MediaPipe + detectores de contexto + streaming
  // al backend (sesión modo:'examen'). Expone score/eventos/eventCount y detener().
  // sessionId alimenta el chat y el flujo de pausa autorizada (C-15).
  const { sessionId, score, eventCount, activo, eventos, extraMonitorActive, detener } = useExamProctoring(videoRef, examen);
  const toast = useToast();

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

  // Toast por CADA evento registrado, del color de su severidad — para que el
  // alumno vea en vivo qué se detectó y cuánto suma (transparencia, "controlado").
  // `eventos` viene newest-first; recorremos al revés para notificar en orden
  // cronológico. Trackeamos ids ya notificados para no repetir en cada render.
  const toastedIds = useRef<Set<string>>(new Set());
  useEffect(() => {
    for (let i = eventos.length - 1; i >= 0; i--) {
      const ev = eventos[i];
      if (toastedIds.current.has(ev.id)) continue;
      toastedIds.current.add(ev.id);
      const sev = ev.severidad as Severidad;
      const tipoToast = SEV_TOAST[sev] ?? 'info';
      const puntos = pesoEvento(ev.tipo, sev);
      const label = TIPO_EVENTO_LABEL[ev.tipo as keyof typeof TIPO_EVENTO_LABEL] ?? ev.tipo;
      toast.show({
        tipo: tipoToast,
        msg: `${label} · ${SEVERIDAD_LABEL[sev] ?? sev} · +${puntos} pts`,
      });
    }
  }, [eventos, toast]);

  // Cierre prolijo: cortar el proctoring antes de navegar (eventos ya persistidos).
  const finalizar = () => {
    detener();
    navigate('/cierre');
  };

  const mm = String(Math.floor(segRestantes / 60)).padStart(2, '0');
  const ss = String(segRestantes % 60).padStart(2, '0');

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
                <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">{PREGUNTA.numero}</p>
                <h2 className="font-headline text-title-lg text-on-surface mt-base">{PREGUNTA.enunciado}</h2>
              </div>
              <span className={`inline-flex items-center gap-base px-sm py-base rounded-lg text-label-md font-bold ${segRestantes < 300 ? 'bg-error-container text-on-error-container' : 'bg-warning-container text-warning'}`}>
                <Icon name="timer" className="text-[18px]" /> {mm}:{ss}
              </span>
            </div>
            <div className="space-y-sm">
              {PREGUNTA.opciones.map((op, i) => (
                <label key={i} className={`flex items-center gap-sm p-md rounded-xl border cursor-pointer transition-all ${
                  opcion === i ? 'border-primary-container bg-primary-fixed/40' : 'border-outline-variant hover:border-primary-container hover:bg-surface-container-low'
                }`}>
                  <input type="radio" name="q" checked={opcion === i} onChange={() => setOpcion(i)} className="w-4 h-4 accent-[#4241bc]" />
                  <span className="text-body-md text-on-surface">{op}</span>
                </label>
              ))}
            </div>
            <div className="flex pt-md border-t border-outline-variant/40">
              <Button icon="check_circle" onClick={finalizar} className="w-full sm:w-auto sm:ml-auto">
                Finalizar y entregar
              </Button>
            </div>
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
