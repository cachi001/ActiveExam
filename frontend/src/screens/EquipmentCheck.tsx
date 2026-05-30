import { useEffect, useRef, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';

type Estado = 'pendiente' | 'verificando' | 'ok' | 'falla';
interface Chk { id: string; label: string; desc: string; icon: string; estado: Estado; }

export default function EquipmentCheck() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [checks, setChecks] = useState<Chk[]>([
    { id: 'camara', label: 'Cámara web', desc: 'Necesaria para verificación y supervisión.', icon: 'videocam', estado: 'pendiente' },
    { id: 'microfono', label: 'Micrófono', desc: 'Detección de ruido ambiente.', icon: 'mic', estado: 'pendiente' },
    { id: 'red', label: 'Conexión a internet', desc: 'Estable para el canal de eventos.', icon: 'wifi', estado: 'pendiente' },
    { id: 'navegador', label: 'Navegador compatible', desc: 'Soporte de WebAssembly y WebGL.', icon: 'web', estado: 'pendiente' },
    { id: 'monitor', label: 'Un solo monitor', desc: 'No se permiten pantallas adicionales.', icon: 'desktop_windows', estado: 'pendiente' },
  ]);

  const set = (id: string, estado: Estado) => setChecks((c) => c.map((x) => (x.id === id ? { ...x, estado } : x)));

  const correr = async () => {
    setChecks((c) => c.map((x) => ({ ...x, estado: 'verificando' })));
    // Cámara + micrófono reales (getUserMedia)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play().catch(() => {}); }
      set('camara', stream.getVideoTracks().length ? 'ok' : 'falla');
      set('microfono', stream.getAudioTracks().length ? 'ok' : 'falla');
    } catch {
      set('camara', 'falla'); set('microfono', 'falla');
    }
    // Red
    set('red', navigator.onLine ? 'ok' : 'falla');
    // Navegador: WebAssembly + WebGL
    const webgl = (() => { try { return !!document.createElement('canvas').getContext('webgl'); } catch { return false; } })();
    set('navegador', typeof WebAssembly === 'object' && webgl ? 'ok' : 'falla');
    // Monitor adicional (Window Management API, opcional)
    try {
      // @ts-expect-error API experimental
      if (window.getScreenDetails) {
        // @ts-expect-error API experimental
        const d = await window.getScreenDetails();
        set('monitor', d.screens.length <= 1 ? 'ok' : 'falla');
      } else {
        set('monitor', 'ok');
      }
    } catch { set('monitor', 'ok'); }
  };

  useEffect(() => {
    correr();
    return () => { streamRef.current?.getTracks().forEach((t) => t.stop()); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const listo = checks.every((c) => c.estado === 'ok');
  const fallas = checks.filter((c) => c.estado === 'falla').length;
  const enCurso = checks.some((c) => c.estado === 'verificando' || c.estado === 'pendiente');

  return (
    <StudentShell step={1}>
      <div className="max-w-3xl mx-auto space-y-lg animate-in fade-in duration-500">
        <div className="text-center space-y-base">
          <h2 className="font-headline text-headline-lg text-on-surface">Chequeo de requisitos</h2>
          <p className="text-body-md text-on-surface-variant">Verificamos tu equipo antes de comenzar. El análisis de visión corre localmente en tu navegador.</p>
        </div>

        <div className="grid md:grid-cols-2 gap-lg">
          <Card padded={false} className="overflow-hidden">
            <div className="relative aspect-video bg-inverse-surface flex items-center justify-center">
              <video ref={videoRef} muted playsInline className="w-full h-full object-cover" />
              <div className="absolute top-3 left-3 inline-flex items-center gap-base bg-error text-on-error text-label-sm font-bold px-sm py-base rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" /> CÁMARA EN VIVO
              </div>
            </div>
            <div className="p-md text-center">
              <p className="text-label-sm text-on-surface-variant">Vista previa local · no se transmite hasta iniciar el examen.</p>
            </div>
          </Card>

          <Card className="space-y-sm">
            {checks.map((c) => (
              <div key={c.id} className="flex items-center gap-sm py-base">
                <div className="w-10 h-10 rounded-xl bg-surface-container flex items-center justify-center text-on-surface-variant shrink-0">
                  <Icon name={c.icon} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-label-md text-on-surface font-semibold">{c.label}</div>
                  <div className="text-label-sm text-on-surface-variant">{c.desc}</div>
                </div>
                {c.estado === 'verificando' && <Icon name="progress_activity" className="ae-spin text-primary" />}
                {c.estado === 'ok' && <Icon name="check_circle" className="text-success" fill />}
                {c.estado === 'falla' && <Icon name="error" className="text-error" fill />}
                {c.estado === 'pendiente' && <Icon name="radio_button_unchecked" className="text-outline-variant" />}
              </div>
            ))}
          </Card>
        </div>

        <div className="flex items-center justify-between flex-wrap gap-md">
          <div className="text-label-md text-on-surface-variant">
            {enCurso ? 'Verificando equipo…'
              : listo ? <span className="text-success font-semibold inline-flex items-center gap-base"><Icon name="check_circle" className="text-[18px]" fill /> Todo en orden</span>
              : <span className="text-warning font-semibold inline-flex items-center gap-base"><Icon name="warning" className="text-[18px]" fill /> {fallas} requisito(s) con observaciones — podés continuar igual (modo demo)</span>}
          </div>
          <div className="flex gap-sm">
            <Button variant="outline" icon="refresh" onClick={correr}>Reintentar</Button>
            <Button icon="arrow_forward" disabled={enCurso} onClick={() => navigate('/consentimiento')}>
              Continuar
            </Button>
          </div>
        </div>
      </div>
    </StudentShell>
  );
}
