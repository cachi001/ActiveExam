import { useState, useEffect } from 'react';
import { StudentShell } from '../ui/shells';
import { Icon, Button, Card } from '../ui/components';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { Term } from '../ui/Term';
import { BiometricCapture } from '../ui/BiometricCapture';
import { computeFaceDescriptor } from '../vision/faceEmbedding';
import { firstDescriptor } from '../vision/descriptorFallback';
import { unlockAudio } from '../ui/biometric/sounds';
import { buildBiometriaProctoringPayload } from '../vision/liveness';
import type { FaceLandmark } from '../vision/VisionEngine';
import {
  COPY_VERIFICADO_PRINCIPAL,
  COPY_VERIFICANDO_PRINCIPAL,
  COPY_REINTENTO_PRINCIPAL,
} from './BiometriaLogic';

// Fases de la pantalla.
// `no_enrolado` aparece cuando el usuario no tiene referencia biométrica vigente
// (debe completar el enrollment en /perfil antes de verificar).
// En modo real (C-59) el gate se deriva del backend (GET referencia/estado).
// En modo demo se deriva de biometriaReferencia local.
type Fase = 'preparar' | 'capturando' | 'verificando' | 'verificado' | 'reintento' | 'no_enrolado' | 'sin_rostro';

// Sin límite de reintentos — el alumno reintenta hasta verificar o abandonar.

export default function Biometria() {
  const navigate = useNavigate();
  // Sesión de proctoring activa para el envío biométrico (C-46, D6).
  const proctoringSessionId = useApp((s) => s.proctoringSessionId);
  const setBiometriaPendientePayload = useApp((s) => s.setBiometriaPendientePayload);
  const [fase, setFase] = useState<Fase>('preparar');
  const [resultado, setResultado] = useState<{ distancia: number; umbral: number } | null>(null);
  const [reintentos, setReintentos] = useState(0); // solo para mostrar el conteo, sin límite

  // ---------------------------------------------------------------------------
  // 6.1 Al montar en fase `preparar`: consultar el estado de referencia del backend
  // si USE_REAL_BACKEND (C-59). En demo: mantener el gate por biometriaReferencia local.
  // ---------------------------------------------------------------------------
  useEffect(() => {
    // C-59: consultar el estado del backend antes de mostrar el botón de inicio.
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
    frames: HTMLCanvasElement[],
    passiveOk: boolean,
    retosResueltos: string[],
    virtualCameraDetected: boolean,
  ) => {
    setFase('verificando');

    // C-67: descriptor 128-d del rostro vivo, probando los frames candidatos hasta
    // que uno enganche. Dato sensible (Ley 25.326): NO se loguea.
    const vivo = await firstDescriptor(frames, computeFaceDescriptor);

    if (!vivo) {
      // No se detectó rostro en el frame (encuadre vacío / baja luz / sin modelo).
      setFase('sin_rostro');
      return;
    }

    let r: { distancia: number; es_match: boolean; umbral: number } | null = null;

    // C-59: solo manda el embedding vivo; el backend identifica por JWT.
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

    // Envío biométrico al backend activeexam (fire-and-forget, C-46 D6). Solo si hay sesión.
    // C-49/C-67 Task 5.4: liveness_ok, retos_resueltos y señal de cámara virtual son
    // REALES (no hardcodeados). buildBiometriaProctoringPayload es la función pura
    // testeable que construye el payload desde las señales reales de BiometricCapture.
    if (verificado) {
      // Dato sensible (Ley 25.326): NO se loguea ni se muestra en UI.
      const payload = buildBiometriaProctoringPayload(
        passiveOk,
        retosResueltos,
        virtualCameraDetected,
        vivo ?? undefined,
      );
      if (proctoringSessionId) {
        // Sesión ya activa (re-verificación durante el examen): envío inmediato.
        // c-78: si el POST falla, NO se descarta — se deja pendiente para que el
        // reintento de `useExamProctoring` lo vuelva a mandar. Antes el catch se
        // lo tragaba y la verificación de identidad desaparecía sin dejar rastro.
        void api
          .enviarBiometriaProctoring(proctoringSessionId, payload)
          .catch(() => setBiometriaPendientePayload(payload));
      } else {
        // Sin sesión aún (flujo normal: biometría precede a la creación de sesión).
        // Guardamos el payload para que useExamProctoring lo envíe al crear la sesión.
        setBiometriaPendientePayload(payload);
      }
    }

    // 6.1 Gate explícito: el examen NO avanza automáticamente tras la verificación.
    // El alumno debe presionar "Continuar al examen" para navegar (D5 de design.md).
    // Reemplaza el setTimeout(navigate, 1400) que avanzaba sin que el alumno confirme.
  };

  const handleCancel = () => {
    setFase('preparar');
  };

  return (
    <StudentShell step={2} backTo="/requisitos" ocultarNavegacion>
      <div className="max-w-2xl lg:max-w-4xl mx-auto space-y-lg animate-in fade-in duration-500">
        <div className="text-center space-y-base">
          <div className="w-14 h-14 rounded-2xl bg-primary-fixed text-primary flex items-center justify-center mx-auto">
            <Icon name="face" className="text-[28px]" fill />
          </div>
          <h2 className="font-headline text-headline-lg text-on-surface">Verificación biométrica de identidad</h2>
          <p className="text-body-md text-on-surface-variant">
            Confirmamos tu identidad comparando tu imagen en vivo con la foto de referencia que registraste.
            El resultado final siempre lo revisa el equipo. Proceso protegido con <Term termKey="liveness">verificación de presencia</Term>.
          </p>
        </div>

        {/* Fase capturando → overlay inmersivo con BiometricCapture */}
        {fase === 'capturando' && (
          <BiometricCapture
            onComplete={(landmarks, frames, passiveOk, retosResueltos, virtualCameraDetected) => {
              void handleComplete(landmarks, frames, passiveOk, retosResueltos, virtualCameraDetected);
            }}
            onCancel={handleCancel}
          />
        )}

        {fase !== 'capturando' && (
          <Card className="flex flex-col lg:flex-row lg:items-center lg:justify-center gap-lg lg:gap-xl">
            {/* Visual del óvalo. En 'preparar' usamos la MISMA guía clara que el paso de
                captura de referencia del perfil (EnrollmentBiometricStep, fase instrucciones)
                para que el "antes de iniciar" se vea consistente entre perfil y examen.
                En verificando/verificado/etc. se muestra la caja-cámara con feedback
                (scanning-ring / borde verde de éxito). */}
            {/* Óvalo: guía antes de capturar ('preparar'), confirmación visual en 'verificado'. */}
            {(fase === 'preparar' || fase === 'verificado') && (
              <div
                className="shrink-0 relative mx-auto flex items-center justify-center"
                style={{ width: 'min(70vw, 220px)', filter: 'drop-shadow(0 8px 20px rgba(16,24,40,0.08))' }}
              >
                {fase === 'preparar' ? (
                  <div
                    className="w-full rounded-[50%] border-2 border-dashed bg-surface-container-high border-outline-variant transition-colors duration-300"
                    style={{ aspectRatio: '3 / 4' }}
                  />
                ) : (
                  <div
                    className="w-full rounded-[50%] border-4 border-success bg-success/10 flex items-center justify-center"
                    style={{ aspectRatio: '3 / 4' }}
                  >
                    <Icon name="verified" className="text-success text-[64px]" fill />
                  </div>
                )}
              </div>
            )}

            <div className="w-full lg:flex-1 lg:max-w-md">

            {fase === 'preparar' && (
              <div className="text-center space-y-md">
                {/* 6.1/6.2: El gate fue validado por el useEffect (estado del backend).
                    Si la fase llegó aquí es porque tiene referencia vigente. */}
                <p className="text-body-md text-on-surface-variant leading-relaxed">
                  Ubicá tu rostro dentro del óvalo, con buena luz y sin nada que lo tape (gorra,
                  anteojos oscuros, barbijo). Incluye <strong>tres gestos simples</strong>: hacé cada uno
                  {' '}<strong>despacio y sostenelo unos segundos</strong> hasta que se complete, para
                  confirmar que sos una persona real.
                </p>
                <Button icon="photo_camera" onClick={() => { unlockAudio(); setFase('capturando'); }}>Iniciar verificación</Button>
              </div>
            )}

            {fase === 'verificando' && (
              <div className="text-center space-y-base text-on-surface-variant">
                <Icon name="progress_activity" className="ae-spin text-primary text-[32px]" />
                {/* 6.4: copy principal sin jerga; fuente: COPY_VERIFICANDO_PRINCIPAL (BiometriaLogic.ts) */}
                <p className="text-body-md">{COPY_VERIFICANDO_PRINCIPAL}</p>
                <p className="text-label-sm text-on-surface-variant/70">Esto puede tardar unos segundos.</p>
              </div>
            )}

            {fase === 'verificado' && (
              <div className="text-center space-y-md">
                <p className="font-headline text-title-lg text-on-surface">¡Identidad confirmada!</p>

                {/* 6.2 / 6.4: copy principal en lenguaje claro — fuente: COPY_VERIFICADO_PRINCIPAL */}
                <p className="text-body-md text-on-surface-variant">{COPY_VERIFICADO_PRINCIPAL}</p>

                {/* 6.5: valores técnicos en detalle OPCIONAL colapsado. Nunca en el copy principal.
                    Embedding nunca se muestra (dato sensible, Ley 25.326). */}
                {resultado && (
                  <div className="text-left max-w-sm mx-auto mt-xs rounded-xl border border-success/30 bg-success/5 overflow-hidden px-md py-sm space-y-sm">
                    <p className="text-label-sm font-semibold text-on-surface flex items-center gap-xs">
                      <Icon name="analytics" className="text-[14px] text-success" />
                      Detalle de la comparación
                    </p>
                    <div className="space-y-xs text-label-sm">
                      <div className="flex items-center justify-between gap-md">
                        <span className="text-on-surface-variant">Coincidencia con tu foto de referencia</span>
                        <span className="font-bold text-success tabular-nums text-base">
                          {Math.round((1 - resultado.distancia) * 100)}%
                        </span>
                      </div>
                      <div className="w-full bg-surface-container-high rounded-full h-2 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-success transition-all duration-700"
                          style={{ width: `${Math.min(100, Math.round((1 - resultado.distancia) * 100))}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between gap-md pt-xs">
                        <span className="text-on-surface-variant">Mínimo requerido</span>
                        <span className="font-semibold text-on-surface-variant tabular-nums">
                          {Math.round((1 - resultado.umbral) * 100)}%
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* 6.1 / 6.2: botón explícito — el examen NO avanza automáticamente */}
                <Button icon="arrow_forward" onClick={() => navigate('/calibracion')}>
                  Continuar al examen
                </Button>
              </div>
            )}

            {fase === 'reintento' && (
              <div className="text-center space-y-md">
                <Icon name="cancel" className="text-error text-[48px]" fill />

                {/* 6.3 / 6.4: copy principal en lenguaje claro — fuente: COPY_REINTENTO_PRINCIPAL */}
                <p className="text-body-md text-on-surface">{COPY_REINTENTO_PRINCIPAL}</p>

                {reintentos > 0 && (
                  <p className="text-label-sm text-on-surface-variant">
                    Intento {reintentos + 1} — podés seguir intentando.
                  </p>
                )}

                {/* 6.5: valores técnicos en detalle OPCIONAL colapsado.
                    Nunca en el copy principal. Embedding nunca se muestra. */}
                {resultado && (
                  <div className="text-left max-w-sm mx-auto mt-xs rounded-xl border border-error/30 bg-error/5 overflow-hidden px-md py-sm space-y-sm">
                    <p className="text-label-sm font-semibold text-on-surface flex items-center gap-xs">
                      <Icon name="analytics" className="text-[14px] text-error" />
                      Detalle de la comparación
                    </p>
                    <div className="space-y-xs text-label-sm">
                      <div className="flex items-center justify-between gap-md">
                        <span className="text-on-surface-variant">Coincidencia con tu foto de referencia</span>
                        <span className="font-bold text-error tabular-nums text-base">
                          {Math.round((1 - resultado.distancia) * 100)}%
                        </span>
                      </div>
                      <div className="w-full bg-surface-container-high rounded-full h-2 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-error transition-all duration-700"
                          style={{ width: `${Math.min(100, Math.round((1 - resultado.distancia) * 100))}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between gap-md pt-xs">
                        <span className="text-on-surface-variant">Mínimo requerido</span>
                        <span className="font-semibold text-on-surface-variant tabular-nums">
                          {Math.round((1 - resultado.umbral) * 100)}%
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                <div className="flex gap-sm justify-center flex-wrap">
                  <Button variant="outline" icon="refresh" onClick={() => setFase('capturando')}>Reintentar</Button>
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
                  No encontramos tu referencia biométrica en el servidor.
                </p>
                <p className="text-label-sm text-on-surface-variant max-w-md mx-auto">
                  Puede pasar si la captura anterior no llegó a guardarse (sin red,
                  rostro no detectado, etc.). Volvé a <strong>Mi perfil</strong> y
                  rehacé la captura de referencia biométrica.
                </p>
                <Button variant="outline" icon="account_circle" onClick={() => navigate('/perfil')}>
                  Ir a mi perfil
                </Button>
              </div>
            )}
            </div>
          </Card>
        )}
      </div>
    </StudentShell>
  );
}
