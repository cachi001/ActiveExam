/**
 * retencionCapturas — fuente única del piso de `retencion_capturas_dias`.
 * Sincronizado con el backend (`app.domain.retention.policy.RETENCION_CAPTURAS_DIAS_MINIMO`
 * y el `field_validator` de `app/presentation/api/v1/config/router.py`): 90 días,
 * decisión del dueño. Las capturas son la evidencia más pesada y sensible (fotos
 * del rostro del alumno tomadas por la cámara; la pantalla NO se captura); bajar
 * el piso arriesga borrar evidencia necesaria antes de que un reclamo pueda
 * resolverse.
 *
 * La pantalla que edita este campo (Configuración → Parámetros generales) debe
 * importar de acá — no duplicar el número. El backend es quien manda: esto es
 * solo para dar feedback inmediato sin esperar el 422 del servidor.
 */

export const RETENCION_CAPTURAS_DIAS_MINIMO = 90;
export const RETENCION_CAPTURAS_DIAS_DEFAULT = 180;
