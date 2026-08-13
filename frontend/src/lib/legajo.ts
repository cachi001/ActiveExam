/**
 * Los usuarios provisionados vía LTI usan `lti:{deployment_id}:{sub}` como
 * `id_institucional` — es la CLAVE INTERNA de idempotencia del JIT, NO un legajo
 * real. Moodle no siempre envía un legajo; cuando no lo tenemos, no hay legajo:
 * no mostramos la clave sintética (`lti:1:8`) como si fuera la matrícula.
 */

/** `true` si el id es la clave sintética que arma el JIT LTI (no un legajo real). */
export function esIdInstitucionalSintetico(id?: string | null): boolean {
  return !!id && id.startsWith('lti:');
}

/** El legajo a MOSTRAR: `null` si no hay legajo real (id sintético o vacío). */
export function legajoVisible(id?: string | null): string | null {
  if (!id || esIdInstitucionalSintetico(id)) return null;
  return id;
}
