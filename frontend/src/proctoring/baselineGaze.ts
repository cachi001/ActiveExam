/**
 * Baseline de mirada calibrado ANTES del examen.
 *
 * ## Por qué existe
 *
 * La calibración de mirada (3 s mirando al centro) corría DENTRO del examen, con
 * el cronómetro ya andando y un cartel que no decía cómo había salido. Dos
 * problemas en uno: le come tiempo al alumno y es una caja negra.
 *
 * Decisión del dueño (29/8/2026): la calibración es UN PASO del ingreso, no algo
 * que pasa en medio de la rendición. Ahora se hace en la sala de espera —el paso
 * 3, justo antes de empezar— y el resultado se guarda acá para que el examen lo
 * use sin volver a calibrar.
 *
 * ## Por qué en memoria y no en el store ni en sessionStorage
 *
 * El baseline describe cómo estaba sentado el alumno HOY, frente a ESTA cámara.
 * Que se pierda al recargar es correcto: si recarga, se recalibra. Y el examen
 * conserva su calibración interna como respaldo para ese caso, así que perderlo
 * nunca deja al alumno sin calibrar.
 */

export interface BaselineGaze {
  x: number;
  y: number;
}

let baseline: BaselineGaze | null = null;

/** Guarda el baseline medido en el paso de calibración. */
export function guardarBaselineGaze(valor: BaselineGaze | null): void {
  baseline = valor;
}

/** El baseline del paso previo, o `null` si no se calibró (o se recargó). */
export function baselineGazeGuardado(): BaselineGaze | null {
  return baseline;
}

/** Lo descarta. Para los tests y para cuando termina la rendición. */
export function olvidarBaselineGaze(): void {
  baseline = null;
}

/**
 * ¿El examen tiene que calibrar por su cuenta?
 *
 * Solo si el paso previo no dejó baseline: recarga a mitad de examen, o alguien
 * que entró por una ruta que se saltea la sala. Es el respaldo, no el camino
 * normal.
 */
export function debeCalibrarEnElExamen(): boolean {
  return baseline === null;
}

/**
 * Cómo describirle al alumno lo que se midió.
 *
 * La calibración era invisible: decía "listo" sin mostrar NADA, así que no se
 * entendía para qué servía ni si había hecho algo. El baseline en crudo
 * (`{x, y}`) no le dice nada a nadie, pero su componente horizontal sí tiene una
 * lectura concreta: **de qué lado quedó la cámara respecto de donde mira**.
 *
 * Eso responde la pregunta de fondo: con la cámara a un costado, calibrar SÍ
 * sirve — el sistema toma esa desviación como el nuevo cero y deja de leerla
 * como "mirada desviada" cuando en realidad estás leyendo.
 */
export type PosicionCamara = 'centrada' | 'izquierda' | 'derecha';

/**
 * A partir de qué desviación horizontal se considera que la cámara está a un
 * costado. Por debajo, la diferencia es ruido de medición y no vale nombrarla.
 */
export const DESVIO_LATERAL_MINIMO = 0.15;

export function posicionDeLaCamara(baseline: BaselineGaze | null): PosicionCamara | null {
  if (!baseline) return null;
  if (Math.abs(baseline.x) < DESVIO_LATERAL_MINIMO) return 'centrada';
  // `x` positivo = la mirada se va hacia la derecha del encuadre para mirar la
  // pantalla, o sea que la cámara quedó a la IZQUIERDA de esa pantalla.
  return baseline.x > 0 ? 'izquierda' : 'derecha';
}
