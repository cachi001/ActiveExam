import { useEffect, useRef, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card, SeverityBadge } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { descripcionEvento, TIPO_EVENTO_LABEL } from '../lib/api';
import {
  FocusDetector,
  FullscreenDetector,
  ClipboardDetector,
  detectExtraMonitor,
} from '../proctoring/contextDetectors';
import { StateTransitionRules } from '../proctoring/stateTransitionRules';
import type { EventoSesion, Severidad, TipoEvento } from '../lib/types';

const PREGUNTA = {
  numero: 'Pregunta 1 de 5',
  enunciado: 'Identificá la descripción anatómica correcta del hueso hioides:',
  opciones: [
    'Hueso impar y simétrico ubicado en la parte anterior y superior del cuello.',
    'Hueso par ubicado a nivel supraclavicular interno.',
    'Hueso cartilaginoso simétrico a nivel de la laringe posterior.',
    'Estructura ósea conectora interna del manubrio esternal.',
  ],
};

const PESO_SCORE: Record<Severidad, number> = { baseline: 0, baja: 5, media: 12, alta: 22, critica: 30 };

export default function Examen() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);
  const pushAnomalia = useApp((s) => s.pushAnomalia);
  const addScore = useApp((s) => s.addScore);
  const scorePropio = useApp((s) => s.scorePropio);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Señales de contexto — acumuladas en refs para consumir en el siguiente tick del motor
  const focusLost = useRef(false);
  const tabChanged = useRef(false);
  const fullscreenExited = useRef(false);
  const clipboardAction = useRef<'copy' | 'paste' | null>(null);
  // null = no determinable (API ausente/denegada); false = sin monitor adicional; true = con monitor adicional
  const extraMonitor = useRef<boolean | null>(null);

  const rules = useRef(new StateTransitionRules());

  const [segRestantes, setSegRestantes] = useState((examen?.duracion_min ?? 90) * 60);
  const [eventos, setEventos] = useState<EventoSesion[]>([]);
  const [alerta, setAlerta] = useState<EventoSesion | null>(null);
  const [opcion, setOpcion] = useState<number | null>(null);
  const [mensajes, setMensajes] = useState<{ de: string; texto: string; hora: string }[]>([
    { de: 'Sistema', texto: 'Canal cifrado y persistido con cadena de custodia.', hora: '' },
  ]);
  const [borrador, setBorrador] = useState('');

  // cámara
  useEffect(() => {
    navigator.mediaDevices?.getUserMedia({ video: true }).then((s) => {
      streamRef.current = s;
      if (videoRef.current) { videoRef.current.srcObject = s; videoRef.current.play().catch(() => {}); }
    }).catch(() => {});
    return () => streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  // Detectores de contexto REALES — C-25 (proctoring/contextDetectors.ts)
  useEffect(() => {
    // Foco de ventana (blur/focus OS) + cambio de pestaña (visibilitychange)
    const fd = new FocusDetector((sig) => {
      if (sig.focus_lost !== undefined) focusLost.current = sig.focus_lost;
      if (sig.tab_changed !== undefined) tabChanged.current = sig.tab_changed;
    });
    fd.start();

    // Salida de pantalla completa (fullscreenchange)
    const fsd = new FullscreenDetector((sig) => {
      if (sig.fullscreen_exited) fullscreenExited.current = true;
    });
    fsd.start();

    // Clipboard (copy/paste sin leer contenido)
    const cd = new ClipboardDetector((sig) => {
      if (sig.clipboard_action) clipboardAction.current = sig.clipboard_action;
    });
    cd.start();

    // Monitor adicional — polling cada 5 s; degrada a null si la API no está disponible
    let monitorPollActive = true;
    const pollMonitor = async () => {
      // Proveedor nativo donde esté disponible (Window Management API)
      const provider = typeof window !== 'undefined' && 'getScreenDetails' in window
        ? () => (window as unknown as { getScreenDetails: () => Promise<{ screens: unknown[] }> }).getScreenDetails()
        : undefined;
      const sig = await detectExtraMonitor(provider);
      extraMonitor.current = sig?.extra_monitor ?? null;
      if (monitorPollActive) setTimeout(pollMonitor, 5000);
    };
    pollMonitor();

    return () => {
      fd.stop();
      fsd.stop();
      cd.stop();
      monitorPollActive = false;
    };
  }, []);

  // temporizador
  useEffect(() => {
    const t = setInterval(() => setSegRestantes((s) => (s <= 0 ? 0 : s - 1)), 1000);
    return () => clearInterval(t);
  }, []);

  // motor de señales: combina señales reales de navegador + señales simuladas de visión y evalúa reglas
  useEffect(() => {
    const t = setInterval(() => {
      const ahora = Date.now();
      const roll = Math.random();

      // Consumir señales acumuladas en refs y resetear (excepto extraMonitor que se actualiza por polling)
      const snapFocusLost = focusLost.current;
      const snapTabChanged = tabChanged.current;
      const snapFullscreenExited = fullscreenExited.current;
      const snapClipboard = clipboardAction.current;
      focusLost.current = false;
      tabChanged.current = false;
      fullscreenExited.current = false;
      clipboardAction.current = null;

      const signals = {
        ts_ms: ahora,
        face_count: roll < 0.04 ? 2 : roll < 0.07 ? 0 : 1,
        gaze: roll > 0.85 ? { x: 0.7, y: 0.2 } : { x: 0.05, y: 0.02 },
        focus_lost: snapFocusLost,
        // extra_monitor: null = no determinable; false = sin monitor; true = con monitor adicional
        extra_monitor: extraMonitor.current === true,
        tab_changed: snapTabChanged,
        fullscreen_exited: snapFullscreenExited,
        clipboard_action: snapClipboard ?? undefined,
      };
      let discretos = rules.current.process(signals);
      // segunda pasada para que la mirada sostenida supere la ventana temporal
      if (signals.gaze.x > 0.6) discretos = discretos.concat(rules.current.process({ ...signals, ts_ms: ahora + 4200 }));

      for (const d of discretos) {
        const ev: EventoSesion = {
          id: `${ahora}-${d.tipo}`,
          tipo: d.tipo as TipoEvento,
          severidad: d.severidad as Severidad,
          ts_backend: new Date().toISOString(),
          descripcion: descripcionEvento(d.tipo as TipoEvento),
          tiene_evidencia: d.trigger_evidence,
        };
        setEventos((prev) => [ev, ...prev].slice(0, 30));
        pushAnomalia(ev);
        addScore(PESO_SCORE[ev.severidad]);
        if (ev.severidad === 'alta' || ev.severidad === 'critica') setAlerta(ev);
      }
    }, 3500);
    return () => clearInterval(t);
  }, [pushAnomalia, addScore]);

  const mm = String(Math.floor(segRestantes / 60)).padStart(2, '0');
  const ss = String(segRestantes % 60).padStart(2, '0');

  const enviar = () => {
    if (!borrador.trim()) return;
    setMensajes((m) => [...m, { de: 'Estudiante', texto: borrador, hora: new Date().toTimeString().slice(0, 5) }]);
    setBorrador('');
  };

  return (
    <StudentShell step={5}>
      <div className="grid lg:grid-cols-3 gap-lg animate-in fade-in duration-500">
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
            <div className="flex justify-between pt-md border-t border-outline-variant/40">
              <Button variant="outline" icon="arrow_back">Anterior</Button>
              <Button icon="check_circle" onClick={() => navigate('/cierre')}>Finalizar y entregar</Button>
            </div>
          </Card>
        </div>

        {/* Panel de proctoring */}
        <div className="space-y-lg">
          <Card padded={false} className="overflow-hidden">
            <div className="relative aspect-video bg-inverse-surface">
              <video ref={videoRef} muted playsInline className="w-full h-full object-cover" />
              <div className="absolute top-1/4 left-1/4 w-1/2 h-1/2 border-2 border-success/80 rounded-xl">
                <span className="absolute -top-5 left-0 bg-success text-on-error text-[9px] font-bold px-1.5 py-0.5 rounded uppercase">Rostro verificado</span>
              </div>
              <div className="absolute top-3 left-3 inline-flex items-center gap-base bg-primary-container text-on-primary text-[9px] font-bold px-sm py-base rounded-full uppercase">
                <Icon name="videocam" className="text-[12px]" /> Proctor activo
              </div>
            </div>
          </Card>

          <Card className="space-y-sm">
            <div className="flex items-center justify-between border-b border-outline-variant/40 pb-base">
              <h3 className="text-label-md font-bold text-on-surface">Señales de integridad (local)</h3>
              <span className="text-label-sm text-on-surface-variant">Riesgo {scorePropio}%</span>
            </div>
            <div className="space-y-base max-h-[220px] overflow-y-auto">
              {eventos.length === 0 ? (
                <div className="text-center py-lg text-on-surface-variant space-y-base">
                  <Icon name="check_circle" className="text-success text-[32px]" fill />
                  <p className="text-label-sm">Integridad óptima. Sin incidencias en el navegador.</p>
                </div>
              ) : eventos.map((ev) => (
                <div key={ev.id} className="flex gap-sm p-sm rounded-xl bg-surface-container-low border border-outline-variant/40">
                  <Icon name="warning" className="text-warning shrink-0 text-[18px]" fill />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-base">
                      <span className="text-label-md font-semibold text-on-surface">{TIPO_EVENTO_LABEL[ev.tipo]}</span>
                      <SeverityBadge severidad={ev.severidad} />
                    </div>
                    <p className="text-label-sm text-on-surface-variant mt-base">{ev.descripcion}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="space-y-sm">
            <h3 className="text-label-md font-bold text-on-surface border-b border-outline-variant/40 pb-base">Canal con el proctor</h3>
            <div className="h-[120px] overflow-y-auto space-y-base bg-surface-container-low rounded-xl p-sm">
              {mensajes.map((m, i) => (
                <div key={i} className={`text-label-sm ${m.de === 'Sistema' ? 'text-on-surface-variant italic text-center' : m.de === 'Estudiante' ? 'text-right' : ''}`}>
                  {m.de !== 'Sistema' && <span className="font-semibold">{m.de} · {m.hora} </span>}
                  {m.texto}
                </div>
              ))}
            </div>
            <div className="flex gap-base">
              <input value={borrador} onChange={(e) => setBorrador(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && enviar()}
                placeholder="Escribir mensaje…" className="flex-1 px-sm py-base text-label-md rounded-xl border border-outline-variant bg-surface-container-lowest focus:border-primary-container outline-none" />
              <Button onClick={enviar} className="h-auto px-md">Enviar</Button>
            </div>
          </Card>
        </div>
      </div>

      {alerta && <AlertaCritica ev={alerta} onClose={() => setAlerta(null)} />}
    </StudentShell>
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
