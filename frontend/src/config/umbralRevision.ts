/**
 * umbralRevision — fuente única del rango válido de umbral_cola_revision.
 * Sincronizado con el backend (Field(ge=70, le=100) en
 * `app/presentation/api/v1/config/router.py`) y con la decisión de producto
 * de no bajar de 70 (nunca sancionar/priorizar con un piso más laxo).
 *
 * El techo de UI (90) es más estricto que el techo del backend (100) por
 * decisión de producto: no tiene sentido revisar solo sesiones casi
 * perfectas. Las pantallas que muestran o editan este umbral (Configuración
 * → Parámetros generales, Test de detección → Medidor de riesgo) deben
 * importar de acá — no duplicar los números.
 */

export const UMBRAL_REVISION_MIN = 70;
export const UMBRAL_REVISION_MAX = 90;
