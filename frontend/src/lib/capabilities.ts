/**
 * Capa de capacidades del frontend (C-71 slice 2, D8) — config-driven.
 *
 * El front SOLO oculta; el backend DECIDE (backstop server-side: `require_capability`
 * en el router de review). Este mapa espeja `CAPABILITY_ROLES` del backend, adaptado
 * al modelo de 3 roles del MVP donde el rol `revisor` está colapsado en `admin_sistema`
 * (ver `types.ts` §Rol). Reasignar una capacidad a otro rol es un cambio de ESTE mapa,
 * sin tocar los componentes que lo consultan.
 */
import type { Rol } from "./types";

export type Capacidad = "revisar_sesion" | "resolver_caso";

/** capacidad → conjunto de roles que la poseen (dato de config, no lógica). */
const CAPABILITY_ROLES: Record<Capacidad, readonly Rol[]> = {
  // El staff que revisa la cola (admin_sistema = revisor en el modelo colapsado).
  revisar_sesion: ["admin_sistema"],
  // Veredicto (anular/descartar). HOY concentrado en el mismo rol; remapeable.
  resolver_caso: ["admin_sistema"],
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
