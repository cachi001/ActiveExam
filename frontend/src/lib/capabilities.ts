/**
 * Capa de capacidades del frontend (C-71 slice 2, D8) — config-driven.
 *
 * El front SOLO oculta; el backend DECIDE (backstop server-side:
 * `require_capability`). Por eso este mapa tiene que ser una COPIA EXACTA de
 * `CAPABILITY_ROLES` en `backend/app/domain/auth/capabilities.py`: si el front
 * es más permisivo, muestra un botón que el backend rechaza con 403; si es más
 * restrictivo, esconde una acción que la persona sí podía hacer.
 *
 * `resolver_caso` (capacidad separada para el veredicto de una segunda fase)
 * DESAPARECIÓ: el modelo de dos fases fue rechazado explícitamente por el
 * owner del proyecto. `revisar_sesion` cubre TODO el acto — aprobar y anular,
 * en un solo paso — porque no hay segunda instancia que gatear aparte.
 * Al tocar este mapa, tocar el del backend en el mismo commit.
 */
import type { Rol } from "./types";

export type Capacidad =
  | "revisar_sesion"
  | "gestionar_academico"
  | "gestionar_notas"
  | "configurar_sistema"
  | "gestionar_usuarios"
  | "ver_auditoria"
  | "supervisar_vivo";

/** capacidad → conjunto de roles que la poseen (dato de config, no lógica). */
const CAPABILITY_ROLES: Record<Capacidad, readonly Rol[]> = {
  revisar_sesion: ["revisor", "coordinador", "admin_sistema"],
  gestionar_academico: ["tutor", "admin_examenes", "coordinador", "admin_sistema"],
  gestionar_notas: ["tutor", "admin_examenes", "coordinador", "admin_sistema"],
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
