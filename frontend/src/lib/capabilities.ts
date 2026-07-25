/**
 * Capa de capacidades del frontend (C-71 slice 2, D8) — config-driven.
 *
 * El front SOLO oculta; el backend DECIDE (backstop server-side:
 * `require_capability`). Por eso este mapa tiene que ser una COPIA EXACTA de
 * `CAPABILITY_ROLES` en `backend/app/domain/auth/capabilities.py`: si el front
 * es más permisivo, muestra un botón que el backend rechaza con 403; si es más
 * restrictivo, esconde una acción que la persona sí podía hacer.
 *
 * Antes decía `resolver_caso: ["admin_sistema"]` "adaptado al modelo de 3 roles
 * del MVP donde el rol revisor está colapsado en admin_sistema" — un colapso que
 * el backend NUNCA hizo: allá `resolver_caso` siempre fue exclusiva de `revisor`.
 * Con esa divergencia, al admin se le habilitaban los botones de anulación y cada
 * click moría en 403, mientras el revisor —el único autorizado— ni entraba.
 * Al tocar este mapa, tocar el del backend en el mismo commit.
 */
import type { Rol } from "./types";

export type Capacidad =
  | "revisar_sesion"
  | "resolver_caso"
  | "gestionar_academico"
  | "gestionar_notas"
  | "configurar_sistema"
  | "gestionar_usuarios"
  | "ver_auditoria"
  | "supervisar_vivo";

/** capacidad → conjunto de roles que la poseen (dato de config, no lógica). */
const CAPABILITY_ROLES: Record<Capacidad, readonly Rol[]> = {
  revisar_sesion: ["revisor", "coordinador", "admin_sistema"],
  // Veredicto (anular/descartar): revisor como autoridad instructora;
  // admin_sistema como autoridad máxima del sistema.
  resolver_caso: ["revisor", "admin_sistema"],
  gestionar_academico: ["docente", "admin_examenes", "coordinador", "admin_sistema"],
  gestionar_notas: ["docente", "admin_examenes", "coordinador", "admin_sistema"],
  configurar_sistema: ["admin_sistema"],
  gestionar_usuarios: ["admin_sistema"],
  ver_auditoria: ["auditor", "admin_sistema"],
  supervisar_vivo: ["proctor", "revisor", "coordinador", "admin_sistema"],
};

/**
 * `true` si alguno de los `roles` posee la `capacidad`. Una capacidad no
 * declarada deniega por defecto (fail-closed), igual que el backend.
 */
export function tieneCapacidad(roles: readonly Rol[], capacidad: Capacidad): boolean {
  const permitidos = CAPABILITY_ROLES[capacidad];
  if (!permitidos) return false;
  return roles.some((r) => permitidos.includes(r));
}
