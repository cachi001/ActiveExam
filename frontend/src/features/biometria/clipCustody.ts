/**
 * Custodia inicial del clip de verificacion en el cliente (C-09, RN-BIO-07).
 *
 * El clip de 3-5 s se HASHEA (SHA-256) y se SUBE DIRECTO al storage por URL firmada
 * (no transita el backend, RN-CC-04, RN-GLB-01). El hash ancla la cadena de
 * custodia inicial; la firma con la clave de sesion la hace el backend al
 * re-inferir (el cliente aun no posee la clave rotativa: nace de la verificacion
 * exitosa). El cliente entrega ``clip_uri`` + ``clip_hash`` al backend, que
 * re-infiere sobre el clip EXACTO.
 *
 * Usa WebCrypto (``crypto.subtle``) — disponible en el navegador. Logica aislada
 * para poder testearla con un digest inyectable.
 */

/** Calcula el SHA-256 (hex) de los bytes del clip via WebCrypto. */
export async function hashClip(
  clipBytes: ArrayBuffer,
  subtle: SubtleCrypto = crypto.subtle,
): Promise<string> {
  const digest = await subtle.digest("SHA-256", clipBytes);
  return bufferToHex(digest);
}

/** Convierte un ArrayBuffer a hex en minusculas (formato del backend). */
export function bufferToHex(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let hex = "";
  for (const b of bytes) {
    hex += b.toString(16).padStart(2, "0");
  }
  return hex;
}

export interface PresignedClip {
  upload_url: string;
  object_key: string;
  expires_in: number;
}

/**
 * Sube el clip DIRECTO al storage por la URL firmada (PUT). No pasa por el backend.
 * ``fetchImpl`` inyectable para tests. Devuelve ``object_key`` para que el cliente
 * arme la ``clip_uri`` que reporta al backend.
 */
export async function uploadClip(
  presigned: PresignedClip,
  clipBytes: ArrayBuffer | Blob,
  fetchImpl: typeof fetch = fetch,
): Promise<string> {
  const resp = await fetchImpl(presigned.upload_url, {
    method: "PUT",
    body: clipBytes as BodyInit,
    headers: { "Content-Type": "application/octet-stream" },
  });
  if (!resp.ok) {
    throw new Error(`Fallo la subida del clip bajo custodia (${resp.status})`);
  }
  return presigned.object_key;
}
