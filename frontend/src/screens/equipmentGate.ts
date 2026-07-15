/**
 * equipmentGate — decisión pura del chequeo de requisitos previo al examen.
 *
 * Separa la REGLA (¿puede avanzar?) de la pantalla `EquipmentCheck`, para que
 * sea testeable sin DOM ni APIs de navegador.
 *
 * Regla dura (pedido del owner): el avance al examen se BLOQUEA salvo que TODOS
 * los requisitos de entorno estén en 'ok'. Cualquier requisito en 'falla',
 * 'pendiente' o 'verificando' impide continuar (fail-closed).
 */

export type EstadoRequisito = 'pendiente' | 'verificando' | 'ok' | 'falla';

export interface RequisitoCheck {
  estado: EstadoRequisito;
}

/** True solo si hay al menos un requisito y TODOS están en 'ok'. */
export function puedeContinuar(checks: RequisitoCheck[]): boolean {
  return checks.length > 0 && checks.every((c) => c.estado === 'ok');
}
