/**
 * Pantalla de verificacion biometrica de identidad (C-09, feature biometria).
 *
 * Ultimo paso pre-examen (Flujo 2, pasos 2-7), DESPUES del gate de consentimiento
 * (C-08). El cliente:
 *  1. captura un video de 3-5 s con instrucciones claras (US-004 CA-1).
 *  2. corre el liveness hibrido: pasivo (parpadeo/micro-mov/profundidad 3D) + 1-2
 *     RETOS ACTIVOS aleatorios (RN-BIO-05, DD-18) + deteccion de camara virtual.
 *  3. calcula el embedding con el motor de vision ABSTRAIDO (DD-17).
 *  4. sube el clip por URL firmada (custodia inicial) y POSTea la referencia al
 *     backend, que RE-INFIERE server-side y decide (RN-GLB-01).
 *
 * El cliente es un SENSOR NO CONFIABLE: su veredicto de liveness/match es una
 * SENAL; el backend re-infiere y emite (o no) la clave de sesion. Hasta 2
 * reintentos; al 3.º fallo el backend escala a proctor SIN abortar (RN-BIO-04).
 *
 * Convencion del proyecto: componente PascalCase; contratos de red en snake_case.
 */

import { useCallback, useMemo, useState } from "react";

import type { VisionEngine } from "../../vision/VisionEngine";
import {
  type ActiveChallenge,
  clientLivenessOk,
  pickActiveChallenges,
} from "../../vision/liveness";
import { hashClip, type PresignedClip, uploadClip } from "./clipCustody";

interface VerifyResponse {
  veredicto: string;
  distancia: number | null;
  reintentos_restantes: number;
  clave_sesion_emitida: boolean;
  escalado_a_proctor: boolean;
  intentos_fallidos: number;
}

interface BiometricVerificationProps {
  sessionId: string;
  authToken: string;
  visionEngine: VisionEngine;
  /** Captura el clip 3-5 s y devuelve sus bytes + los frames procesados. */
  captureClip: () => Promise<{ bytes: ArrayBuffer; frameCount: number }>;
  /** Funcion que, dados los frames, devuelve las senales de liveness del cliente. */
  evaluateLiveness: (requested: ActiveChallenge[]) => Promise<{
    livenessOk: boolean;
    virtualCamera: boolean;
    solved: ActiveChallenge[];
  }>;
  apiBase?: string;
  onVerified?: () => void;
  onEscalated?: () => void;
}

export function BiometricVerification({
  sessionId,
  authToken,
  visionEngine,
  captureClip,
  evaluateLiveness,
  apiBase = "/api/v1",
  onVerified,
  onEscalated,
}: BiometricVerificationProps) {
  const [status, setStatus] = useState<string>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(null);
  // Retos activos ALEATORIOS por intento (RN-BIO-05). Se re-eligen en cada intento.
  const [challenges, setChallenges] = useState<ActiveChallenge[]>(() =>
    pickActiveChallenges(2),
  );

  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    }),
    [authToken],
  );

  const runVerification = useCallback(async () => {
    setError(null);
    setStatus("capturando");
    try {
      // 1. Captura del clip 3-5 s.
      const { bytes } = await captureClip();

      // 2. Liveness hibrido: pasivo + retos activos + camara virtual.
      setStatus("liveness");
      const liveness = await evaluateLiveness(challenges);
      const clientOk = clientLivenessOk({
        // El gate fino lo recalcula el backend; aqui solo guiamos al usuario.
        passive: {
          parpadeo_detectado: liveness.livenessOk,
          micro_movimientos: liveness.livenessOk,
          profundidad_3d_coherente: liveness.livenessOk,
        },
        requested: challenges,
        solved: liveness.solved,
        virtualCameraDetected: liveness.virtualCamera,
      });

      // 3. Hash del clip (custodia inicial) + presign + subida directa al storage.
      setStatus("custodia");
      const clipHash = await hashClip(bytes);
      const presigned = await presignClip(sessionId, apiBase, headers);
      const objectKey = await uploadClip(presigned, bytes);
      
      // 4. Verificacion final server-side.


      if (data.clave_sesion_emitida) {
        setStatus("verificado");
        onVerified?.();
      } else if (data.escalado_a_proctor) {
        setStatus("escalado");
        onEscalated?.();
      } else {
        // Reintento disponible: re-elige retos activos aleatorios (anti-ensayo).
        setStatus("reintentar");
        setChallenges(pickActiveChallenges(2));
      }
    } catch (e) {
      setError(String(e));
      setStatus("error");
    }
  }, [
    apiBase, authToken, captureClip, challenges, evaluateLiveness, headers,
    onEscalated, onVerified, sessionId,
  ]);

  return (
    <section aria-labelledby="bio-title" className="biometric-verification">
      <h1 id="bio-title">Verificación de identidad</h1>
      <p>
        Vamos a grabar un video corto (3–5 s) para confirmar tu identidad. Seguí
        las instrucciones en pantalla y completá los gestos que se te pidan.
      </p>

      <ul className="bio-challenges" aria-label="Retos a completar">
        {challenges.map((c) => (
          <li key={c}>{CHALLENGE_LABELS[c] ?? c}</li>
        ))}
      </ul>

      {error && <div role="alert">Error: {error}</div>}

      {result && !result.clave_sesion_emitida && !result.escalado_a_proctor && (
        <p role="status">
          No pudimos confirmar tu identidad. Te quedan{" "}
          {result.reintentos_restantes} reintento(s). Probá de nuevo.
        </p>
      )}
      {result?.escalado_a_proctor && (
        <p role="status">
          No pudimos confirmar tu identidad automáticamente. Un proctor humano va a
          revisar tu caso. El examen no se cancela.
        </p>
      )}
      {result?.clave_sesion_emitida && (
        <p role="status">Identidad confirmada. Ya podés comenzar el examen.</p>
      )}

      <button
        type="button"
        onClick={runVerification}
        disabled={
          status === "capturando" ||
          status === "liveness" ||
          status === "custodia" ||
          status === "verificando" ||
          status === "verificado" ||
          status === "escalado"
        }
      >
        {status === "reintentar" ? "Reintentar verificación" : "Iniciar verificación"}
      </button>
    </section>
  );
}

const CHALLENGE_LABELS: Record<string, string> = {
  girar_izquierda: "Girá la cabeza a la izquierda",
  girar_derecha: "Girá la cabeza a la derecha",
  parpadear: "Parpadeá cuando se te indique",
  acercarse: "Acercate un poco a la cámara",
  sonreir: "Sonreí",
};

/** Pide al backend la URL firmada para subir el clip (custodia inicial). */
async function presignClip(
  sessionId: string,
  apiBase: string,
  headers: Record<string, string>,
): Promise<PresignedClip> {
  const resp = await fetch(
    `${apiBase}/identity/presign-clip?session_id=${encodeURIComponent(sessionId)}`,
    { method: "POST", headers },
  );
  if (!resp.ok) {
    throw new Error(`No se pudo obtener la URL firmada del clip (${resp.status})`);
  }
  return resp.json();
}

export default BiometricVerification;
