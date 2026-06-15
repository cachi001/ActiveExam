/**
 * descriptorFallback — robustez en la extracción del descriptor facial 128-d
 * (C-67 fix).
 *
 * El descriptor se obtiene con face-api (tinyFaceDetector), un modelo DISTINTO al
 * MediaPipe que valida los gestos. Sobre un único frame, si ese modelo no engancha
 * la cara, devuelve null y la captura falla con "Error en la captura" — aunque los
 * gestos hayan salido perfectos. `firstDescriptor` prueba varios frames candidatos
 * y devuelve el PRIMER descriptor válido, dándole a face-api múltiples chances.
 *
 * Es lógica pura (no toca el DOM ni importa face-api): recibe la función de cómputo
 * por parámetro, así se testea sin navegador ni modelos.
 */

/**
 * Recorre los frames candidatos y devuelve el primer descriptor 128-d que se
 * pueda extraer. Saltea frames nulos y absorbe errores transitorios de inferencia
 * (un frame que falla no aborta: pasa al siguiente). Devuelve null si ninguno sirve.
 */
export async function firstDescriptor(
  frames: Array<HTMLCanvasElement | null | undefined>,
  compute: (frame: HTMLCanvasElement) => Promise<number[] | null>,
): Promise<number[] | null> {
  for (const frame of frames) {
    if (!frame) continue;
    try {
      const descriptor = await compute(frame);
      if (descriptor && descriptor.length > 0) return descriptor;
    } catch {
      // Error transitorio de inferencia en este frame → probar el siguiente.
    }
  }
  return null;
}
