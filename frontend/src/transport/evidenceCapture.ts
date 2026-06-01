/**
 * Captura y custodia de evidencia en el cliente (C-12 + C-24, etapa 1, RN-CC-01/02/04).
 *
 * CAMBIO C-24 (DD-24-01): el artefacto de evidencia automática PASA de CLIP de
 * video (5-10 s) a SCREENSHOT (frame único). Motivación: proporcionalidad L2.5 y
 * minimización de datos (Ley 25.326). Ver design.md de c-24-evidencia-screenshots.
 *
 * ZONA NO CONFIABLE — cliente = sensor no confiable.
 * Ante un disparador (evento severo O heartbeat), captura un único frame del
 * <video> vía canvas, calcula ``hash_cliente = SHA-256(screenshot)`` y
 * ``firma_cliente = HMAC(clave_sesion, hash_cliente)``, pide una URL firmada de
 * PUT y sube el binario DIRECTO al storage (no transita el backend). Luego
 * notifica al backend la metadata + hash + firma; el backend re-hashea y valida
 * (etapa 2 de la cadena).
 *
 * CADENA DE CUSTODIA (DD-24-03, RN-CC-02):
 *   1. Cliente (aquí): SHA-256(frame) + HMAC(clave_sesion, hash) → presigned PUT.
 *   2. Backend: valida firma, re-calcula hash, persiste metadata, audit log, WORM.
 *   3. Worker / clave maestra: 3.ª verificación de hash, firma asimétrica
 *      (RSA-2048 / Ed25519), re-inferencia ESTÁTICA sobre el frame (DD-24-01,
 *      DD-24-03) — detección de objetos/rostros en la imagen, sin contexto
 *      temporal (tradeoff aceptado L2.5).
 *
 * RE-INFERENCIA SERVER-SIDE (documentado, fuera del scope del cliente):
 *   El worker re-descarga el screenshot exacto desde WORM, corre detección
 *   estática (face detection / object detection sobre la imagen), compara con
 *   los labels/confidences reportados por el cliente en EvidenceNotification y
 *   firma el resultado. Una discrepancia es señal forense de posible tampering;
 *   NO dispara sanción automática (L2.5 — la decisión es siempre humana).
 *
 * NO hay grabación de video continuo en ningún punto de la sesión (C-24, 1.4).
 *
 * ``subtle``/``fetchImpl`` inyectables para tests sin DOM/red.
 */

import { hashClip, uploadClip, type PresignedClip } from "../features/biometria/clipCustody";

// Re-exportar PresignedClip para que los consumidores no dependan de clipCustody directamente.
export type { PresignedClip };

/** Severidades que disparan captura de evidencia (RN-CC-01). */
const SEVERIDADES_SEVERAS = new Set(["alta", "critica"]);

/** Tipo de disparador de la captura (C-24, DD-24-02). */
export type EvidenceTriggerKind = "event" | "heartbeat";

/** True sii la severidad dispara captura de evidencia (alta/critica). */
export function disparaCaptura(severidad: string): boolean {
  return SEVERIDADES_SEVERAS.has(severidad);
}

/**
 * Notificación enviada al backend tras una captura de evidencia.
 * El backend la usa para la etapa 2 de la cadena de custodia (RN-CC-02).
 *
 * CAMBIO C-24: se añaden ``trigger`` (event | heartbeat) y ``severidad``
 * para que el backend clasifique el screenshot en la cola de revisión.
 * Los campos preexistentes son retrocompatibles con el contrato de C-12.
 */
export interface EvidenceNotification {
  session_id: string;
  exam_id: string;
  object_key: string;
  hash_cliente: string;
  firma_cliente: string;
  /** C-24: tipo de disparador que originó este screenshot. */
  trigger: EvidenceTriggerKind;
  /** C-24: severidad del evento que originó el screenshot (vacío para heartbeat). */
  severidad?: string;
}

/** Firma HMAC-SHA256 (hex) del hash del screenshot con la clave de sesion (RN-CC-02). */
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

// Alias semántico para C-24 (el algoritmo es idéntico, cambia el nombre del artefacto).
export const firmarScreenshot = firmarClip;

/**
 * Captura un frame único del elemento <video> como Blob PNG (C-24, tarea 1.1).
 *
 * Dibuja el frame actual del video en un canvas oculto y devuelve el Blob.
 * NO graba video; la captura es atómica (un único frame).
 *
 * @param videoEl - Elemento <video> con el stream activo.
 * @param quality  - Calidad JPEG si se usa image/jpeg (0..1). Por defecto PNG sin pérdida.
 * @returns ArrayBuffer con los bytes de la imagen PNG.
 * @throws si el video no tiene dimensiones válidas o el canvas no puede generar el blob.
 */
export async function capturarFrame(
  videoEl: HTMLVideoElement,
  mimeType: "image/png" | "image/jpeg" = "image/png",
  quality = 0.92,
): Promise<ArrayBuffer> {
  const w = videoEl.videoWidth;
  const h = videoEl.videoHeight;
  if (!w || !h) {
    throw new Error("capturarFrame: video sin dimensiones válidas — ¿stream activo?");
  }
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("capturarFrame: no se pudo obtener contexto 2D del canvas");
  ctx.drawImage(videoEl, 0, 0, w, h);

  return new Promise<ArrayBuffer>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) { reject(new Error("capturarFrame: toBlob devolvió null")); return; }
        blob.arrayBuffer().then(resolve).catch(reject);
      },
      mimeType,
      mimeType === "image/jpeg" ? quality : undefined,
    );
  });
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
 * Ejecuta la etapa 1 de la cadena ante un evento severo (C-12 + C-24):
 * recibe los bytes del screenshot ya capturado, hashea, firma, sube directo
 * por presigned URL y devuelve la notificación para el backend.
 *
 * Devuelve ``null`` si la severidad no es severa (RN-CC-01) y el trigger es
 * "event"; para trigger "heartbeat" siempre ejecuta (la cadencia ya validó
 * que debe capturarse).
 *
 * NOTA: la captura del frame (<video> → canvas) es responsabilidad del
 * llamador (ej. evidenceCadence.ts); esta función solo opera sobre bytes.
 * Esto mantiene la lógica de captura separable y testeable sin DOM.
 */
export async function capturarEvidencia(
  severidad: string,
  screenshotBytes: ArrayBuffer,
  deps: CaptureDeps,
  trigger: EvidenceTriggerKind = "event",
): Promise<EvidenceNotification | null> {
  // Solo los eventos alta/critica disparan captura event-driven (RN-CC-01).
  // Heartbeats siempre pasan (la cadencia ya los filtró).
  if (trigger === "event" && !disparaCaptura(severidad)) return null;

  const subtle = deps.subtle ?? crypto.subtle;
  const hash = await hashClip(screenshotBytes, subtle);
  const firma = await firmarScreenshot(hash, deps.sessionKey, subtle);
  const presigned = await deps.presign();
  const objectKey = await uploadClip(presigned, screenshotBytes, deps.fetchImpl ?? fetch);

  return {
    session_id: deps.sessionId,
    exam_id: deps.examId,
    object_key: objectKey,
    hash_cliente: hash,
    firma_cliente: firma,
    trigger,
    severidad: trigger === "event" ? severidad : undefined,
  };
}
