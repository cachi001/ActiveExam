/**
 * captureVideoFrame — helper puro para capturar el frame actual de un <video>
 * como base64 JPEG (C-46, capability: video-frame-capture).
 *
 * SIN dependencias de React, MediaPipe ni CameraSnapshotCapture.
 * Importable desde cualquier contexto: hook, callback de setInterval, Web Worker.
 *
 * DATO SENSIBLE (Ley 25.326): el resultado base64 es una imagen del alumno.
 * Quien lo use NO debe loguearlo en consola ni persistirlo en localStorage.
 */

/**
 * Captura el frame actual de un HTMLVideoElement y lo retorna como dataURL JPEG.
 *
 * @param videoEl - Elemento <video> con el stream activo.
 * @param quality - Calidad JPEG entre 0 y 1 (default: 0.7).
 * @returns dataURL `data:image/jpeg;base64,...` o `null` si el frame no está listo.
 *
 * Retorna null si:
 * - `videoEl.readyState < 2` (HAVE_CURRENT_DATA no alcanzado)
 * - Las dimensiones del video son cero
 * - Se produce cualquier excepción interna (sin propagar)
 */
export function captureVideoFrame(
  videoEl: HTMLVideoElement,
  quality: number = 0.7,
): string | null {
  try {
    // Verificar que el video tiene un frame válido listo
    if (videoEl.readyState < 2) return null;
    const w = videoEl.videoWidth;
    const h = videoEl.videoHeight;
    if (!w || !h) return null;

    // Crear canvas temporal efímero — no queda en el DOM
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.drawImage(videoEl, 0, 0);
    return canvas.toDataURL('image/jpeg', quality ?? 0.7);
  } catch {
    // Cualquier excepción (SecurityError en canvas tainted, etc.) → null sin propagar
    return null;
  }
}
