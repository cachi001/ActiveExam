import { useEffect, useRef, useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api, DESAFIOS } from '../lib/api';
import { pickActiveChallenges } from '../vision/liveness';
import type { DesafioActivo } from '../lib/types';

type Fase = 'preparar' | 'capturando' | 'verificando' | 'verificado' | 'reintento';

export default function Biometria() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [fase, setFase] = useState<Fase>('preparar');
  const [desafios, setDesafios] = useState<DesafioActivo[]>([]);
  const [resueltos, setResueltos] = useState<string[]>([]);
  const [resultado, setResultado] = useState<{ distancia: number; reintentos: number } | null>(null);

  useEffect(() => {
    navigator.mediaDevices?.getUserMedia({ video: true }).then((s) => {
      streamRef.current = s;
      if (videoRef.current) { videoRef.current.srcObject = s; videoRef.current.play().catch(() => {}); }
    }).catch(() => {});
    return () => streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  const iniciar = () => {
    // pickActiveChallenges es lógica REAL del cliente (vision/liveness.ts, RN-BIO-05)
    const ids = pickActiveChallenges(2);
    setDesafios(ids.map((id) => DESAFIOS.find((d) => d.id === id)!).filter(Boolean));
    setResueltos([]);
    setFase('capturando');
  };

  const resolver = (id: string) => {
    const next = [...resueltos, id];
    setResueltos(next);
    if (next.length >= desafios.length) verificar();
  };

  const verificar = async () => {
    setFase('verificando');
    const r = await api.verifyIdentity(examen?.id ?? 'SESS-DEMO', 0.31);
    setResultado({ distancia: r.distancia, reintentos: r.reintentos_restantes });
    setFase(r.veredicto === 'verificado' ? 'verificado' : 'reintento');
    if (r.veredicto === 'verificado') setTimeout(() => navigate('/sala-espera'), 1400);
  };

  return (
    <StudentShell step={3}>
      <div className="max-w-2xl mx-auto space-y-lg animate-in fade-in duration-500">
        <div className="text-center space-y-base">
          <div className="w-14 h-14 rounded-2xl bg-primary-fixed text-primary flex items-center justify-center mx-auto">
            <Icon name="face" className="text-[28px]" fill />
          </div>
          <h2 className="font-headline text-headline-lg text-on-surface">Verificación biométrica de identidad</h2>
          <p className="text-body-md text-on-surface-variant">
            Verificación 1:1 contra tu foto institucional con liveness híbrido (ISO 30107-3). El backend re-infiere y firma el resultado.
          </p>
        </div>

        <Card className="flex flex-col items-center gap-lg">
          <div className="relative w-[280px] h-[340px] rounded-[40px] overflow-hidden bg-inverse-surface flex items-center justify-center">
            <video ref={videoRef} muted playsInline className="absolute inset-0 w-full h-full object-cover" />
            <div className={`relative w-[180px] h-[240px] rounded-[50%] border-2 border-dashed ${fase === 'verificado' ? 'border-success' : 'border-primary-container'} ${fase === 'capturando' || fase === 'verificando' ? 'scanning-ring' : ''}`} />
            <div className="absolute bottom-3 left-3 inline-flex items-center gap-base bg-error text-on-error text-label-sm font-bold px-sm py-base rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" /> CÁMARA EN VIVO
            </div>
          </div>

          {fase === 'preparar' && (
            <div className="text-center space-y-md">
              <p className="text-body-md text-on-surface-variant">Encuadrá tu rostro dentro del óvalo y mantené buena iluminación.</p>
              <Button icon="photo_camera" onClick={iniciar}>Iniciar verificación</Button>
            </div>
          )}

          {fase === 'capturando' && (
            <div className="w-full space-y-sm">
              <p className="text-label-md text-on-surface text-center font-semibold">Realizá los siguientes gestos (anti-suplantación):</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-sm">
                {desafios.map((d) => {
                  const hecho = resueltos.includes(d.id);
                  return (
                    <button key={d.id} disabled={hecho} onClick={() => resolver(d.id)}
                      className={`flex items-center gap-sm p-sm rounded-xl border transition-all ${
                        hecho ? 'bg-success-container border-success/30 text-success' : 'bg-surface-container-low border-outline-variant hover:border-primary-container'
                      }`}>
                      <Icon name={hecho ? 'check_circle' : 'gesture'} fill={hecho} />
                      <span className="text-label-md font-semibold">{d.label}</span>
                    </button>
                  );
                })}
              </div>
              <p className="text-label-sm text-on-surface-variant text-center">(Demo: tocá cada gesto para simular su detección)</p>
            </div>
          )}

          {fase === 'verificando' && (
            <div className="text-center space-y-base text-on-surface-variant">
              <Icon name="progress_activity" className="ae-spin text-primary text-[32px]" />
              <p className="text-body-md">Re-inferencia server-side y verificación 1:1…</p>
            </div>
          )}

          {fase === 'verificado' && (
            <div className="text-center space-y-base">
              <Icon name="verified" className="text-success text-[40px]" fill />
              <p className="font-headline text-title-lg text-on-surface">¡Identidad confirmada!</p>
              <p className="text-label-sm text-on-surface-variant">Distancia {resultado?.distancia} · clave de sesión efímera emitida</p>
            </div>
          )}

          {fase === 'reintento' && (
            <div className="text-center space-y-md">
              <Icon name="error" className="text-error text-[40px]" fill />
              <p className="text-body-md text-on-surface">No hubo coincidencia suficiente. Te quedan {resultado?.reintentos} intentos.</p>
              <div className="flex gap-sm justify-center">
                <Button variant="outline" icon="refresh" onClick={iniciar}>Reintentar</Button>
                <Button variant="ghost" icon="support_agent" onClick={() => navigate('/sala-espera')}>Escalar a proctor</Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </StudentShell>
  );
}
