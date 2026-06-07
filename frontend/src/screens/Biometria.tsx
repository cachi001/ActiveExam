import { useState, useEffect } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api, USE_REAL_BACKEND } from '../lib/api';
import { Term } from '../ui/Term';
import { BiometricCapture } from '../ui/BiometricCapture';
import { computeFaceDescriptor } from '../vision/faceEmbedding';
import type { FaceLandmark } from '../vision/VisionEngine';

// Fases de la pantalla.
// `no_enrolado` aparece cuando el usuario no tiene referencia biométrica vigente
// (debe completar el enrollment en /perfil antes de verificar).
// En modo real (C-59) el gate se deriva del backend (GET referencia/estado).
// En modo demo se deriva de biometriaReferencia local.
type Fase = 'preparar' | 'capturando' | 'verificando' | 'verificado' | 'reintento' | 'no_enrolado' | 'sin_rostro';

const MAX_REINTENTOS = 2;

export default function Biometria() {
  const navigate = useNavigate();
  // Sesión de proctoring activa para el envío biométrico (C-46, D6).
  const proctoringSessionId = useApp((s) => s.proctoringSessionId);
  // Referencia biométrica 128-d local (solo se usa en modo DEMO).
  // En modo real es null por diseño (C-56): el embedding se guarda cifrado en el backend.
  // NO se loguea (Ley 25.326, dato sensible).
  const biometriaReferencia = useApp((s) => s.biometriaReferencia);

  const [fase, setFase] = useState<Fase>('preparar');
  const [resultado, setResultado] = useState<{ distancia: number; umbral: number } | null>(null);
  const [reintentos, setReintentos] = useState(0);

  // ---------------------------------------------------------------------------
  // 6.1 Al montar en fase `preparar`: consultar el estado de referencia del backend
  // si USE_REAL_BACKEND (C-59). En demo: mantener el gate por biometriaReferencia local.
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!USE_REAL_BACKEND) return; // Demo: el gate lo maneja el render (biometriaReferencia local).

    // Modo real (C-59): consultar el estado del backend antes de mostrar el botón de inicio.
    let canceled = false;
    void (async () => {
      try {
        const estado = await api.estadoReferenciaBiometrica();
        if (!canceled && !estado.tiene_referencia_vigente) {
          setFase('no_enrolado');
        }
        // Si tiene referencia vigente: la fase queda en 'preparar' (botón habilitado).
      } catch {
        // Error de red: no cambiar la fase; el gate `preparar` mostrará el botón
        // y si no hay referencia el backend responderá 404 en verificar-referencia.
      }
    })();
    return () => { canceled = true; };
  }, []);

  // ---------------------------------------------------------------------------
  // handleComplete — descriptor "vivo" REAL (face-api) sobre el frame capturado.
  //
  // RAMA REAL (USE_REAL_BACKEND=1, C-59):
  //   - No bloquea por biometriaReferencia (es null por diseño en modo real, C-56).
  //   - Captura el embedding vivo y llama a verificarBiometriaReferencia.
  //   - 404 del backend -> fase no_enrolado (sin referencia).
  //   - es_match=false -> fase reintento.
  //   - es_match=true -> fase verificado + navega a /sala-espera.
  //
  // RAMA DEMO (USE_REAL_BACKEND=0):
  //   - Mantiene el gate por biometriaReferencia local.
  //   - Llama a api.verificarBiometria con el embedding local (comparación coseno local).
  //
  // D3 (C-49): firma ampliada — recibe liveness pasivo real, retos resueltos reales
  // y flag de cámara virtual.
  // ---------------------------------------------------------------------------
  const handleComplete = async (
    _landmarks: FaceLandmark[],
    frame: HTMLCanvasElement | null,
    passiveOk: boolean,
    retosResueltos: string[],
    virtualCameraDetected: boolean,
  ) => {
    // 6.2 RAMA DEMO: gate de enrolamiento por referencia local.
    // En modo real NO se aplica este gate (biometriaReferencia es null por diseño).
    if (!USE_REAL_BACKEND && (!biometriaReferencia || biometriaReferencia.length === 0)) {
      setFase('no_enrolado');
      return;
    }

    setFase('verificando');

    // Descriptor 128-d del rostro vivo. Dato sensible (Ley 25.326): NO se loguea.
    const vivo = frame ? await computeFaceDescriptor(frame) : null;

    if (!vivo) {
      // No se detectó rostro en el frame (encuadre vacío / baja luz / sin modelo).
      setFase('sin_rostro');
      return;
    }

    let r: { distancia: number; es_match: boolean; umbral: number } | null = null;

    if (USE_REAL_BACKEND) {
      // 6.2 Rama real (C-59): solo manda el embedding vivo; el backend identifica por JWT.
      // biometriaReferencia es null intencionalmente y NO se referencia aquí.
      // 6.4 El embedding vivo es dato sensible (Ley 25.326): NO se loguea.
      try {
        r = await api.verificarBiometriaReferencia(vivo);
      } catch (err) {
        // 6.3 Distinguir 404 (sin referencia) de error de red.
        const statusCode = (err as { status?: number })?.status ??
          (err instanceof Response ? err.status : undefined);
        if (statusCode === 404) {
          // 6.3 Sin referencia vigente -> enviar a enrollment.
          setFase('no_enrolado');
          return;
        }
        // Error de red u otro: tratar como reintento honesto.
        setFase('reintento');
        setReintentos((n) => n + 1);
        return;
      }
    } else {
      // Rama demo: comparación coseno local con el embedding de referencia del store.
      r = await api.verificarBiometria(vivo, biometriaReferencia ?? []);
    }

    if (!r) {
      // Backend no respondió → tratar como reintento honesto.
      setFase('reintento');
      setReintentos((n) => n + 1);
      return;
    }

    setResultado({ distancia: r.distancia, umbral: r.umbral });
    // 6.3 es_match=true -> verificado + navegar; es_match=false -> reintento.
    const verificado = r.es_match;

    if (verificado) {
      setFase('verificado');
      setReintentos(0);
    } else {
      setFase('reintento');
      setReintentos((n) => n + 1);
    }

    // Envío biométrico al backend slim (fire-and-forget, C-46 D6). Solo si hay sesión.
    // C-49: liveness_ok y retos_resueltos ahora son REALES (no hardcodeados).
    if (verificado && proctoringSessionId) {
      void api.enviarBiometriaProctoring(proctoringSessionId, {
        liveness_ok: passiveOk,
        retos_resueltos: retosResueltos,
        // El embedding viaja al backend slim para su re-inferencia/firma (C-12).
        embedding: vivo,
        resultado: virtualCameraDetected ? 'camara_virtual_detectada' : 'verificado',
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
            onComplete={(landmarks, frame, passiveOk, retosResueltos, virtualCameraDetected) => {
              void handleComplete(landmarks, frame, passiveOk, retosResueltos, virtualCameraDetected);
            }}
            onCancel={handleCancel}
          />
        )}

        {fase !== 'capturando' && (
          <Card className="flex flex-col items-center gap-lg">
            <div className="relative w-[280px] h-[340px] rounded-[40px] overflow-hidden bg-inverse-surface flex items-center justify-center">
              <div className={`relative w-[180px] h-[240px] rounded-[50%] border-2 border-dashed ${fase === 'verificado' ? 'border-success' : 'border-primary-container'} ${fase === 'verificando' ? 'scanning-ring' : ''}`} />
            </div>

            {fase === 'preparar' && (
              <div className="text-center space-y-md">
                {/* 6.1/6.2: En modo real el gate fue validado por el useEffect (estado del backend).
                    Si la fase llegó aquí es porque tiene referencia vigente (o es demo con referencia).
                    En demo sin referencia local: mostrar CTA a /perfil. */}
                {USE_REAL_BACKEND || biometriaReferencia ? (
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
