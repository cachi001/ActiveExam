/**
 * faceEmbedding — descriptor facial REAL de 128 dimensiones con face-api.js
 * (fork @vladmandic/face-api, mantenido y compatible con Vite/ESM).
 *
 * Provee el embedding de identidad que la verificación biométrica 1:1 compara
 * contra la referencia capturada en el enrollment. A diferencia del
 * pseudo-embedding geométrico de Face Mesh (que no es comparable 1:1), el
 * descriptor de faceRecognitionNet es un vector de 128 floats entrenado para
 * que la distancia (coseno/euclídea) entre dos caras de la MISMA persona sea
 * baja y entre personas distintas sea alta.
 *
 * MODELOS (en /public/models, servidos como estáticos por Vite):
 * - tinyFaceDetector  (detector liviano de rostros)
 * - faceLandmark68Net (68 landmarks para alinear el rostro antes del descriptor)
 * - faceRecognitionNet (el de 128-d — produce el descriptor de identidad)
 *
 * DATO SENSIBLE (Ley 25.326): el descriptor de 128-d es dato biométrico sensible.
 * NUNCA se loguea ni se persiste en claro fuera del store/localStorage de la demo.
 * El cliente es SENSOR NO CONFIABLE (RN-GLB-01): el backend re-infiere y firma;
 * acá solo se computa la SEÑAL para la comparación 1:1.
 *
 * DEGRADACIÓN ELEGANTE: ensureModelsLoaded() rechaza con el error original si los
 * modelos no cargan (sin WebGL, 404, red). Los callers caen a un estado claro,
 * no crashean — mismo patrón de fallback que BiometricCapture.
 */

import * as faceapi from '@vladmandic/face-api';

const MODEL_URL = '/models';

// Carga perezosa: una sola vez por sesión. Reusa la promesa en vuelo para evitar
// dobles cargas si dos pantallas piden modelos en simultáneo.
let modelsLoadedPromise: Promise<void> | null = null;

/**
 * Precarga (idempotente) los tres modelos necesarios para el descriptor 128-d.
 * Si ya están cargados, resuelve de inmediato. Si falla, propaga el error
 * original (NO swallow) para que el caller muestre el estado de fallback.
 */
export async function ensureModelsLoaded(): Promise<void> {
  if (modelsLoadedPromise !== null) return modelsLoadedPromise;

  modelsLoadedPromise = (async () => {
    try {
      await Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
        faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
        faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
      ]);
    } catch (err) {
      // Limpiar para permitir reintento en una próxima llamada.
      modelsLoadedPromise = null;
      throw err;
    }
  })();

  return modelsLoadedPromise;
}

/**
 * Computa el descriptor facial de 128-d para el rostro presente en `input`.
 *
 * Corre detectSingleFace (tinyFaceDetector) + landmarks 68 + descriptor 128-d.
 * Devuelve un array plano de 128 floats listo para enviar al backend, o `null`
 * si no se detecta ningún rostro (encuadre vacío, baja luz, etc.).
 *
 * No loguea el descriptor (dato sensible). No lanza: ante error de inferencia
 * devuelve null para que el caller decida (reintento / fallback).
 */
export async function computeFaceDescriptor(
  input: HTMLVideoElement | HTMLCanvasElement | HTMLImageElement,
): Promise<number[] | null> {
  await ensureModelsLoaded();

  try {
    const result = await faceapi
      .detectSingleFace(input, new faceapi.TinyFaceDetectorOptions())
      .withFaceLandmarks()
      .withFaceDescriptor();

    if (!result || !result.descriptor) return null;

    // descriptor es Float32Array de longitud 128 → array plano de números.
    return Array.from(result.descriptor);
  } catch {
    // Error de inferencia transitorio → tratado como "sin rostro detectado".
    return null;
  }
}
