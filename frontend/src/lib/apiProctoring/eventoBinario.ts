// Envío de un evento de detección con la captura BINARIA (c-78 §16.5).
//
// El camino JSON (`enviarEventoProctoring`) manda la imagen como data URL: base64
// son 4 bytes de texto por cada 3 de imagen, y encima el JSON escapa el string. Con
// 100 alumnos subiendo capturas durante dos horas por el enlace de su casa, ese
// tercio de más se paga en tiempo de subida.
//
// Acá la imagen viaja cruda en un multipart y el prefijo del data URL va aparte,
// para que el servidor reconstruya el string EXACTO antes de hashear. Eso es lo que
// no se puede romper: `screenshot_sha256` se calcula sobre ese string y sostiene la
// cadena de custodia. Un prefijo perdido o normalizado no da error visible — da un
// hash distinto, o sea evidencia que no verifica, descubierta recién cuando alguien
// impugna una nota.
//
// DATO SENSIBLE (Ley 25.326): la imagen se transmite solo al backend; nunca se
// loguea ni se persiste en almacenamiento local.
import { API_BASE } from '../apiCore';
import { authProvider } from '../authProvider';
import { fetchAutenticado } from '../fetchAutenticado';
import type { EventoProctoringPayload } from './sesion';
import type { VeredictoReinferencia } from '../types';

/** El backend usa severidad en masculino; el frontend, en femenino + baseline.
 *  Sin este mapeo el POST da 422 y el evento se pierde en silencio. */
const SEVERIDAD_BACKEND: Record<string, string> = {
  baseline: 'bajo',
  baja: 'bajo',
  media: 'medio',
  alta: 'alto',
  critica: 'critico',
};

export interface AcuseEvento {
  evento_id: string;
  veredicto_reinferencia: VeredictoReinferencia;
  face_count_servidor: number;
  screenshot_sha256: string;
}

/** Parte `data:image/png;base64,AAAA` en prefijo y bytes.
 *
 *  El prefijo se devuelve SIN la coma final, que es la forma que el servidor
 *  reconstruye. Un data URL ilegible devuelve `null` en vez de tirar: perder el
 *  registro de que algo pasó es peor que perder la imagen (L2.5). */
export function separarDataUrl(
  dataUrl: string | null | undefined,
): { prefijo: string; bytes: Uint8Array<ArrayBuffer> } | null {
  if (!dataUrl) return null;
  const corte = dataUrl.lastIndexOf(',');
  if (corte === -1) return null;

  const prefijo = dataUrl.slice(0, corte);
  try {
    const binario = atob(dataUrl.slice(corte + 1));
    // `new ArrayBuffer(...)` explícito: `new Uint8Array(n)` se tipa como
    // `Uint8Array<ArrayBufferLike>`, que incluye `SharedArrayBuffer` y no es un
    // `BlobPart` válido para TypeScript.
    const bytes = new Uint8Array(new ArrayBuffer(binario.length));
    for (let i = 0; i < binario.length; i += 1) bytes[i] = binario.charCodeAt(i);
    return { prefijo, bytes };
  } catch {
    return null; // base64 roto: el evento se manda igual, sin captura
  }
}

export async function enviarEventoProctoringBinario(
  sessionId: string,
  payload: EventoProctoringPayload,
): Promise<AcuseEvento> {
  const cuerpo = new FormData();
  cuerpo.set('tipo', payload.tipo);
  cuerpo.set('severidad', SEVERIDAD_BACKEND[payload.severidad] ?? payload.severidad);
  cuerpo.set('ts_cliente', payload.ts_cliente);
  if (payload.face_count_cliente != null) {
    cuerpo.set('face_count_cliente', String(payload.face_count_cliente));
  }
  if (payload.screenshot_sha256_cliente) {
    cuerpo.set('screenshot_sha256_cliente', payload.screenshot_sha256_cliente);
  }

  const imagen = separarDataUrl(payload.screenshot_base64);
  if (imagen) {
    cuerpo.set('screenshot_prefijo', imagen.prefijo);
    cuerpo.set('captura', new Blob([imagen.bytes]), 'captura');
  }

  const token = authProvider.getToken();
  // `fetchAutenticado`, NUNCA `fetch` crudo: el access token vive 15 minutos y el
  // examen dura dos horas, así que a mitad de la rendición vence y todos los
  // eventos empezarían a responder 401 en silencio. El wrapper refresca y reintenta.
  // (Hay un test de arquitectura que falla si alguien vuelve a armar el Bearer a
  // mano; lo agarró en este mismo módulo mientras se escribía.)
  //
  // OJO: sin `Content-Type`. Lo pone el navegador con el boundary del multipart;
  // fijarlo a mano deja el body sin separar y el backend responde 422.
  const respuesta = await fetchAutenticado(
    `${API_BASE}/proctoring/sessions/${encodeURIComponent(sessionId)}/events/binario`,
    {
      method: 'POST',
      body: cuerpo,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  );

  if (!respuesta.ok) {
    // PROPAGA, igual que el camino JSON: dar por enviado lo que no llegó vaciaría
    // el buffer sin haber mandado nada y la resiliencia ante cortes sería
    // decorativa. Quien decide qué hacer con el fallo es el llamador, que tiene el
    // buffer; esta capa solo informa la verdad.
    const error = new Error(`HTTP ${respuesta.status}`) as Error & { status?: number };
    error.status = respuesta.status;
    throw error;
  }
  return (await respuesta.json()) as AcuseEvento;
}
