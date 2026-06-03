import { useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { Term } from '../ui/Term';
import { BiometricCapture } from '../ui/BiometricCapture';
import { computeFaceDescriptor } from '../vision/faceEmbedding';
import type { FaceLandmark } from '../vision/VisionEngine';

// Fases de la pantalla. `no_enrolado` aparece cuando no hay referencia biométrica
// capturada (el alumno debe completar el enrollment en su perfil primero).
type Fase = 'preparar' | 'capturando' | 'verificando' | 'verificado' | 'reintento' | 'no_enrolado' | 'sin_rostro';

const MAX_REINTENTOS = 2;

export default function Biometria() {
  const navigate = useNavigate();
  // Sesión de proctoring activa para el envío biométrico (C-46, D6).
  const proctoringSessionId = useApp((s) => s.proctoringSessionId);
  // Referencia biométrica 128-d capturada en el enrollment (store + localStorage).
  const biometriaReferencia = useApp((s) => s.biometriaReferencia);

  const [fase, setFase] = useState<Fase>('preparar');
  const [resultado, setResultado] = useState<{ distancia: number; umbral: number } | null>(null);
  const [reintentos, setReintentos] = useState(0);

  // ---------------------------------------------------------------------------
  // handleComplete — descriptor "vivo" REAL (face-api) sobre el frame capturado,
  // comparado contra la referencia del enrollment via api.verificarBiometria.
  // ---------------------------------------------------------------------------
  const handleComplete = async (_landmarks: FaceLandmark[], frame: HTMLCanvasElement | null) => {
    // Gate de enrolamiento: sin referencia no hay nada contra qué comparar.
    if (!biometriaReferencia || biometriaReferencia.length === 0) {
      setFase('no_enrolado');
      return;
    }

    setFase('verificando');

    // Descriptor 128-d del rostro vivo. Dato sensible (Ley 25.326): no se loguea.
    const vivo = frame ? await computeFaceDescriptor(frame) : null;

    if (!vivo) {
      // No se detectó rostro en el frame (encuadre vacío / baja luz / sin modelo).
      setFase('sin_rostro');
      return;
    }

    // Comparación 1:1 — real (backend) o mock (distancia coseno local).
    const r = await api.verificarBiometria(vivo, biometriaReferencia);

    if (!r) {
      // Backend no respondió y no hay fallback → tratar como reintento honesto.
      setFase('reintento');
      setReintentos((n) => n + 1);
      return;
    }

    setResultado({ distancia: r.distancia, umbral: r.umbral });
    const verificado = r.es_match;

    if (verificado) {
      setFase('verificado');
      setReintentos(0);
    } else {
      setFase('reintento');
      setReintentos((n) => n + 1);
    }

    // Envío biométrico al backend slim (fire-and-forget, C-46 D6). Solo si hay sesión.
    if (verificado && proctoringSessionId) {
      void api.enviarBiometriaProctoring(proctoringSessionId, {
        liveness_ok: true,
        retos_resueltos: [],
        // El embedding viaja al backend slim para su re-inferencia/firma (C-12).
        embedding: vivo,
        resultado: 'verificado',
      }).catch(() => {
        // Error silencioso: la biometría no debe bloquear el flujo de examen.
      });
    }

    if (verificado) setTimeout(() => navigate('/sala-espera'), 1400);
  };

  const handleCancel = () => {
    setFase('preparar');
  };

  // Distancia formateada para mostrar (3 decimales) sin exponer el vector.
  const distanciaFmt = resultado ? resultado.distancia.toFixed(3) : '—';
  const umbralFmt = resultado ? resultado.umbral.toFixed(2) : '0.35';
  const sinIntentos = reintentos >= MAX_REINTENTOS;

  return (
    <StudentShell step={3}>
      <div className="max-w-2xl mx-auto space-y-lg animate-in fade-in duration-500">
        <div className="text-center space-y-base">
          <div className="w-14 h-14 rounded-2xl bg-primary-fixed text-primary flex items-center justify-center mx-auto">
            <Icon name="face" className="text-[28px]" fill />
          </div>
          <h2 className="font-headline text-headline-lg text-on-surface">Verificación biométrica de identidad</h2>
          <p className="text-body-md text-on-surface-variant">
            Verificación 1:1 contra tu referencia capturada con <Term termKey="liveness">liveness híbrido</Term> (ISO 30107-3). El backend re-infiere y firma el resultado.
          </p>
        </div>

        {/* Fase capturando → overlay inmersivo con BiometricCapture */}
        {fase === 'capturando' && (
          <BiometricCapture
            onComplete={(landmarks, frame) => { void handleComplete(landmarks, frame); }}
            onCancel={handleCancel}
            contextLabel="Verificación de identidad"
          />
        )}

        {fase !== 'capturando' && (
          <Card className="flex flex-col items-center gap-lg">
            <div className="relative w-[280px] h-[340px] rounded-[40px] overflow-hidden bg-inverse-surface flex items-center justify-center">
              <div className={`relative w-[180px] h-[240px] rounded-[50%] border-2 border-dashed ${fase === 'verificado' ? 'border-success' : 'border-primary-container'} ${fase === 'verificando' ? 'scanning-ring' : ''}`} />
            </div>

            {fase === 'preparar' && (
              <div className="text-center space-y-md">
                {biometriaReferencia ? (
                  <>
                    <p className="text-body-md text-on-surface-variant">Encuadrá tu rostro dentro del óvalo y mantené buena iluminación.</p>
                    <Button icon="photo_camera" onClick={() => setFase('capturando')}>Iniciar verificación</Button>
                  </>
                ) : (
                  <>
                    <p className="text-body-md text-on-surface-variant">
                      No encontramos una referencia biométrica registrada. Completá la captura de referencia
                      en tu perfil antes de verificar tu identidad.
                    </p>
                    <Button icon="account_circle" variant="outline" onClick={() => navigate('/perfil')}>Ir a mi perfil</Button>
                  </>
                )}
              </div>
            )}

            {fase === 'verificando' && (
              <div className="text-center space-y-base text-on-surface-variant">
                <Icon name="progress_activity" className="ae-spin text-primary text-[32px]" />
                <p className="text-body-md">Verificando identidad…</p>
                <p className="text-label-sm">Comparación 1:1 del descriptor facial contra tu referencia.</p>
              </div>
            )}

            {fase === 'verificado' && (
              <div className="text-center space-y-base">
                <Icon name="verified" className="text-success text-[40px]" fill />
                <p className="font-headline text-title-lg text-on-surface">¡Identidad confirmada!</p>
                <p className="text-label-sm text-on-surface-variant">
                  Distancia {distanciaFmt} &lt; umbral {umbralFmt} · clave de sesión efímera emitida
                </p>
              </div>
            )}

            {fase === 'reintento' && (
              <div className="text-center space-y-md">
                <Icon name="error" className="text-error text-[40px]" fill />
                <p className="text-body-md text-on-surface">
                  No hubo coincidencia suficiente (distancia {distanciaFmt} ≥ umbral {umbralFmt}).
                  {sinIntentos
                    ? ' Agotaste los reintentos automáticos.'
                    : ` Te ${MAX_REINTENTOS - reintentos === 1 ? 'queda' : 'quedan'} ${MAX_REINTENTOS - reintentos} intento${MAX_REINTENTOS - reintentos === 1 ? '' : 's'}.`}
                </p>
                <div className="flex gap-sm justify-center">
                  {!sinIntentos && (
                    <Button variant="outline" icon="refresh" onClick={() => setFase('capturando')}>Reintentar</Button>
                  )}
                  <Button variant="ghost" icon="support_agent" onClick={() => navigate('/sala-espera')}>Escalar a proctor</Button>
                </div>
              </div>
            )}

            {fase === 'sin_rostro' && (
              <div className="text-center space-y-md">
                <Icon name="face_retouching_off" className="text-warning text-[40px]" fill />
                <p className="text-body-md text-on-surface">
                  No se detectó tu rostro con claridad. Mejorá la iluminación, acercate al óvalo y reintentá.
                </p>
                <Button variant="outline" icon="refresh" onClick={() => setFase('capturando')}>Reintentar</Button>
              </div>
            )}

            {fase === 'no_enrolado' && (
              <div className="text-center space-y-md">
                <Icon name="badge" className="text-error text-[40px]" fill />
                <p className="text-body-md text-on-surface">
                  No hay una referencia biométrica registrada en tu perfil. Es necesaria para comparar tu identidad.
                </p>
                <Button variant="outline" icon="account_circle" onClick={() => navigate('/perfil')}>Ir a mi perfil</Button>
              </div>
            )}
          </Card>
        )}
      </div>
    </StudentShell>
  );
}
