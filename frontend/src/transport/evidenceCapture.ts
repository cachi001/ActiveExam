/**
 * Captura y custodia de evidencia en el cliente (C-12, etapa 1, RN-CC-01/02/04).
 *
 * Zona NO CONFIABLE. Ante un evento de severidad ALTA o CRITICA (solo entonces),
 * captura un clip de 5-10 s, calcula ``hash_cliente = SHA-256(clip)`` y
 * ``firma_cliente = HMAC(clave_sesion, hash_cliente)``, pide una URL firmada de PUT y
 * sube el binario DIRECTO al storage (no transita el backend). Luego notifica al
 * backend la metadata + hash + firma; el backend re-hashea y valida (etapa 2).
 *
 * El clip de verificacion biometrica usa la MISMA cadena (mismo hash + firma + upload
 * directo): ``capturarEvidencia`` es el unico camino de custodia inicial.
 *
 * ``subtle``/``fetchImpl`` inyectables para tests sin DOM/red.
 */

import { hashClip, uploadClip, type PresignedClip } from "../features/biometria/clipCustody";

/** Severidades que disparan captura de evidencia (RN-CC-01). */
const SEVERIDADES_SEVERAS = new Set(["alta", "critica"]);

export interface EvidenceNotification {
  session_id: string;
  exam_id: string;
  object_key: string;
  hash_cliente: string;
  firma_cliente: string;
}

/** True sii la severidad dispara captura de evidencia (alta/critica). */
export function disparaCaptura(severidad: string): boolean {
  return SEVERIDADES_SEVERAS.has(severidad);
}

/** Firma HMAC-SHA256 (hex) del hash del clip con la clave de sesion (RN-CC-02). */
export async function firmarClip(
  clipHash: string,
  sessionKey: string,
  subtle: SubtleCrypto = crypto.subtle,
): Promise<string> {
  const enc = new TextEncoder();
  const key = await subtle.importKey(
    "raw",
    enc.encode(sessionKey),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await subtle.sign("HMAC", key, enc.encode(clipHash));
  let out = "";
  for (const b of new Uint8Array(sig)) out += b.toString(16).padStart(2, "0");
  return out;
}

export interface CaptureDeps {
  sessionId: string;
  examId: string;
  sessionKey: string;
  /** Solicita la URL firmada de PUT al backend. */
  presign: (objectKeyHint?: string) => Promise<PresignedClip>;
  subtle?: SubtleCrypto;
  fetchImpl?: typeof fetch;
}

/**
 * Ejecuta la etapa 1 de la cadena ante un evento severo: hashea, firma, sube directo
 * y devuelve la notificacion para el backend. Devuelve ``null`` si la severidad no es
 * severa (no se captura evidencia, RN-CC-01).
 */
export async function capturarEvidencia(
  severidad: string,
  clipBytes: ArrayBuffer,
  deps: CaptureDeps,
): Promise<EvidenceNotification | null> {
  if (!disparaCaptura(severidad)) return null;
  const subtle = deps.subtle ?? crypto.subtle;
  const hash = await hashClip(clipBytes, subtle);
  const firma = await firmarClip(hash, deps.sessionKey, subtle);
  const presigned = await deps.presign();
  const objectKey = await uploadClip(presigned, clipBytes, deps.fetchImpl ?? fetch);
  return {
    session_id: deps.sessionId,
    exam_id: deps.examId,
    object_key: objectKey,
    hash_cliente: hash,
    firma_cliente: firma,
  };
}
