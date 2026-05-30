/**
 * Firma HMAC de eventos/heartbeats en el cliente (C-10, RN-HB-01, RN-GLB-01).
 *
 * El cliente firma cada evento con la CLAVE DE SESION ROTATIVA (emitida por C-09
 * tras la verificacion biometrica). El MENSAJE CANONICO debe ser identico al del
 * backend (``app.domain.events.signature.mensaje_canonico``): mismo orden, mismo
 * separador. El backend RE-VALIDA y re-firma (el cliente es sensor no confiable).
 *
 * Usa WebCrypto HMAC-SHA256. Logica aislada (clave + subtle inyectables) para
 * testearla sin DOM.
 */

/** Campos minimos del evento para construir el mensaje canonico firmado. */
export interface SignableEvent {
  id: string;
  session_id: string;
  exam_id: string;
  tipo: string;
  severidad: string;
  ts_client: string;
  schema_version: number;
}

const SEP = "|";

/** Mensaje canonico a firmar (mismo orden que el backend, sin ts_backend/firma). */
export function canonicalMessage(ev: SignableEvent): string {
  return [
    ev.id,
    ev.session_id,
    ev.exam_id,
    ev.tipo,
    ev.severidad,
    ev.ts_client,
    String(ev.schema_version),
  ].join(SEP);
}

/** Firma HMAC-SHA256 (hex) del mensaje canonico con la clave de sesion (hex). */
export async function signEvent(
  ev: SignableEvent,
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
  const sig = await subtle.sign("HMAC", key, enc.encode(canonicalMessage(ev)));
  return hex(sig);
}

function hex(buffer: ArrayBuffer): string {
  let out = "";
  for (const b of new Uint8Array(buffer)) out += b.toString(16).padStart(2, "0");
  return out;
}
