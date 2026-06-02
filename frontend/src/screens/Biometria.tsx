import { useState } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { Term } from '../ui/Term';
import { BiometricCapture } from '../ui/BiometricCapture';
import { embeddingFromLandmarks } from '../vision/MediaPipeVisionEngine';
import type { FaceLandmark } from '../vision/VisionEngine';

type Fase = 'preparar' | 'capturando' | 'verificando' | 'verificado' | 'reintento';

export default function Biometria() {
  const navigate = useNavigate();
  const examen = useApp((s) => s.examenActivo);
  // C-46: leer sessionId de proctoring activa para envío biométrico (D6)
  const proctoringSessionId = useApp((s) => s.proctoringSessionId);
  const [fase, setFase] = useState<Fase>('preparar');
  const [resultado, setResultado] = useState<{ distancia: number; reintentos: number } | null>(null);

  // Task 7.3: handleComplete — calcula embedding y llama verificar()
  const handleComplete = async (landmarks: FaceLandmark[]) => {
    // El embedding es un dato sensible (Ley 25.326): se calcula aquí y se
    // pasará al backend para re-inferencia server-side (RN-GLB-01, C-12).
    // embeddingFromLandmarks produce 3 × N_landmarks floats — el backend
    // de producción lo comprimirá vía PCA/capa densa a la dimensión canónica.
    // En el mock API, verifyIdentity no usa el embedding todavía (preparando C-09).
    embeddingFromLandmarks(landmarks); // cálculo real — valor ignorado hasta C-09 real
    await verificar();
  };

  const verificar = async () => {
    setFase('verificando');
    // En el mock API, verifyIdentity no usa el embedding (lo ignora).
    // Con C-09 real, se pasará el embedding calculado en handleComplete.
    const r = await api.verifyIdentity(examen?.id ?? 'SESS-DEMO', 0.31);
    setResultado({ distancia: r.distancia, reintentos: r.reintentos_restantes });
    const verificado = r.veredicto === 'verificado';
    setFase(verificado ? 'verificado' : 'reintento');

    // C-46: envío biométrico al backend slim (fire-and-forget, D6)
    // Solo si hay una sesión de proctoring activa. Error silencioso — no bloquea el flujo.
    if (verificado && proctoringSessionId) {
      void api.enviarBiometriaProctoring(proctoringSessionId, {
        liveness_ok: true,
        retos_resueltos: [], // liveness híbrido real en C-09
        resultado: r.veredicto,
      }).catch(() => {
        // Error silencioso: la biometría real no debe bloquear el flujo de examen
      });
    }

    // Task 7.7: navegación a /sala-espera tras verificado
    if (verificado) setTimeout(() => navigate('/sala-espera'), 1400);
  };

  // Task 7.4: handleCancel — vuelve a la fase preparar
  const handleCancel = () => {
    setFase('preparar');
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
            Verificación 1:1 contra tu foto institucional con <Term termKey="liveness">liveness híbrido</Term> (ISO 30107-3). El backend re-infiere y firma el resultado.
          </p>
        </div>

        {/* Task 7.5: fase capturando → overlay inmersivo con BiometricCapture */}
        {fase === 'capturando' && (
          <BiometricCapture
            onComplete={(landmarks) => { void handleComplete(landmarks); }}
            onCancel={handleCancel}
            contextLabel="Verificación de identidad"
          />
        )}

        {/* Task 7.6: fases preparar, verificando, verificado, reintento sin cambios */}
        {fase !== 'capturando' && (
          <Card className="flex flex-col items-center gap-lg">
            <div className="relative w-[280px] h-[340px] rounded-[40px] overflow-hidden bg-inverse-surface flex items-center justify-center">
              <div className={`relative w-[180px] h-[240px] rounded-[50%] border-2 border-dashed ${fase === 'verificado' ? 'border-success' : 'border-primary-container'} ${fase === 'verificando' ? 'scanning-ring' : ''}`} />
            </div>

            {fase === 'preparar' && (
              <div className="text-center space-y-md">
                <p className="text-body-md text-on-surface-variant">Encuadrá tu rostro dentro del óvalo y mantené buena iluminación.</p>
                <Button icon="photo_camera" onClick={() => setFase('capturando')}>Iniciar verificación</Button>
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
                  <Button variant="outline" icon="refresh" onClick={() => setFase('capturando')}>Reintentar</Button>
                  <Button variant="ghost" icon="support_agent" onClick={() => navigate('/sala-espera')}>Escalar a proctor</Button>
                </div>
              </div>
            )}
          </Card>
        )}
      </div>
    </StudentShell>
  );
}
