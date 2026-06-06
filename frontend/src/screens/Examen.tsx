import { useEffect, useRef, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card, SeverityBadge } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { TIPO_EVENTO_LABEL } from '../lib/api';
import { useExamProctoring } from '../proctoring/useExamProctoring';
import type { EventoSesion } from '../lib/types';

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

export default function Examen() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [segRestantes, setSegRestantes] = useState((examen?.duracion_min ?? 60) * 60);
  const [alerta, setAlerta] = useState<EventoSesion | null>(null);
  const [opcion, setOpcion] = useState<number | null>(null);
  const [mensajes, setMensajes] = useState<{ de: string; texto: string; hora: string }[]>([
    { de: 'Sistema', texto: 'Canal cifrado y persistido con cadena de custodia.', hora: '' },
  ]);
  const [borrador, setBorrador] = useState('');

  // Proctoring REAL de fondo: motor MediaPipe + detectores de contexto + streaming
  // al backend (sesión modo:'examen'). Expone score/eventos/eventCount y detener().
  const { score, eventCount, activo, eventos, detener } = useExamProctoring(videoRef, examen);

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
  const lastAlertaId = useRef<string | null>(null);
  useEffect(() => {
    const critico = eventos.find((e) => e.severidad === 'alta' || e.severidad === 'critica');
    if (critico && critico.id !== lastAlertaId.current) {
      lastAlertaId.current = critico.id;
      setAlerta(critico);
    }
  }, [eventos]);

  // Cierre prolijo: cortar el proctoring antes de navegar (eventos ya persistidos).
  const finalizar = () => {
    detener();
    navigate('/cierre');
  };

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
              <Button icon="check_circle" onClick={finalizar}>Finalizar y entregar</Button>
            </div>
          </Card>
        </div>

        {/* Panel de proctoring */}
        <div className="space-y-lg">
          <Card padded={false} className="overflow-hidden">
            <div className="relative aspect-video bg-inverse-surface">
              <video ref={videoRef} muted playsInline className="w-full h-full object-cover" />
              {/* La detección sigue corriendo en segundo plano (useExamProctoring);
                  no se dibuja ningún marco/overlay sobre el video para no confundir. */}
              <div className="absolute top-3 left-3 inline-flex items-center gap-base bg-primary-container text-on-primary text-[9px] font-bold px-sm py-base rounded-full uppercase">
                <Icon name="videocam" className="text-[12px]" /> Proctor activo
              </div>
              {/* Indicador discreto de supervisión real en vivo */}
              <div className="absolute bottom-3 left-3 inline-flex items-center gap-base bg-inverse-surface/70 text-inverse-on-surface text-[9px] font-semibold px-sm py-base rounded-full">
                <span className={`w-1.5 h-1.5 rounded-full ${activo ? 'bg-success animate-pulse' : 'bg-on-surface-variant'}`} />
                Supervisión activa · {eventCount} eventos
              </div>
            </div>
          </Card>

          <Card className="space-y-sm">
            <div className="flex items-center justify-between border-b border-outline-variant/40 pb-base">
              <h3 className="text-label-md font-bold text-on-surface">Señales de integridad (en vivo)</h3>
              <span className="text-label-sm text-on-surface-variant">Riesgo {score}%</span>
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
