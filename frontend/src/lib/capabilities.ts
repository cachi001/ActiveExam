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
  | "crear_examenes"
  | "gestionar_banco"
  | "gestionar_estructura"
  | "gestionar_notas"
  | "ver_estadisticas"
  | "configurar_sistema"
  | "gestionar_usuarios"
  | "ver_auditoria"
  | "supervisar_vivo";

/** capacidad → conjunto de roles que la poseen (dato de config, no lógica). */
const CAPABILITY_ROLES: Record<Capacidad, readonly Rol[]> = {
  // c-76: "revisor" eliminado; el coordinador absorbe el veredicto.
  // c-78 D11: 'profesor' queda AFUERA de revisar_sesion a propósito — es lo que
  // lo distingue del coordinador: mira la evidencia, no emite el veredicto.
  revisar_sesion: ["coordinador", "admin_sistema"],
  gestionar_academico: ["tutor", "profesor", "coordinador", "admin_sistema"],
  // c-78: CREAR exámenes y el BANCO se separaron de `gestionar_academico`. El
  // tutor conserva leer su catálogo, inscribir y cerrar notas, pero pierde la
  // creación: armar el examen es trabajo del profesor.
  crear_examenes: ["profesor", "coordinador", "admin_sistema"],
  gestionar_banco: ["profesor", "coordinador", "admin_sistema"],
  // Materias, comisiones y PADRÓN (inscribir/desinscribir). SIN tutor: el tutor
  // no toca nada de Materias y comisiones — ni crea, ni edita, ni inscribe.
  // Acompaña su comisión, cierra notas y supervisa. El profesor sí administra.
  gestionar_estructura: ["profesor", "coordinador", "admin_sistema"],
  gestionar_notas: ["tutor", "profesor", "coordinador", "admin_sistema"],
  // Deliberadamente SIN tutor: los filtros de /stats son query params libres sin
  // scoping por comisión.
  ver_estadisticas: ["profesor", "coordinador", "admin_sistema"],
  configurar_sistema: ["admin_sistema"],
  gestionar_usuarios: ["admin_sistema"],
  // c-76-2: "auditor" eliminado; queda exclusiva de admin_sistema (nunca hubo
  // un endpoint real conectado a esta capacidad para "auditor" en el backend).
  ver_auditoria: ["admin_sistema"],
  // c-76: "proctor" eliminado; el coordinador absorbe la supervisión global y
  // el tutor supervisa acotado a su comisión (D2, bloque 8) — el scoping por
  // comisión lo aplica el backend (autorizar_supervision_vivo_sobre_sesion),
  // acá solo se decide si el botón/ruta se muestra.
  supervisar_vivo: ["tutor", "profesor", "coordinador", "admin_sistema"],
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

/** Descripción en castellano llano de cada capacidad — se usa para mostrar
 * los permisos REALES de un rol en el formulario de alta/edición de usuarios
 * (en vez de una frase vaga de una línea por rol). */
export const CAPACIDAD_LABELS: Record<Capacidad, string> = {
  revisar_sesion: 'Revisar sesiones y decidir el veredicto (aprobar o anular)',
  gestionar_academico: 'Ver el catálogo académico (materias, comisiones y exámenes)',
  crear_examenes: 'Crear y configurar exámenes',
  gestionar_banco: 'Gestionar el banco de preguntas de la materia',
  ver_estadisticas: 'Ver las estadísticas institucionales',
  gestionar_estructura: 'Crear y editar materias y comisiones, e inscribir alumnos',
  gestionar_notas: 'Sincronizar notas con Moodle',
  configurar_sistema: 'Configurar el sistema (umbrales, detectores, retención)',
  gestionar_usuarios: 'Gestionar usuarios y roles',
  ver_auditoria: 'Ver el registro de auditoría',
  // Nombra las DOS cosas que habilita. Decía solo "Supervisar exámenes en vivo" y
  // el registro de sesiones quedaba invisible: al mirar los permisos del TUTOR no
  // aparecía por ningún lado, y parecía que no podía consultar lo que pasó en los
  // exámenes de sus comisiones. Sí puede, y siempre pudo — el backend lo acota a
  // las comisiones donde figura como tutor (`comision_tutor`).
  supervisar_vivo: 'Supervisar exámenes en vivo y ver el registro de sesiones (solo de sus comisiones)',
};

/** Módulo/dominio de cada capacidad — agrupa por la ENTIDAD sobre la que se
 * actúa (no por rol), igual al patrón de Sistema-de-Gestion-Convenios
 * (`Permiso.modulo`): agrupar por dominio hace más fácil entender de un
 * vistazo QUÉ PARTE del sistema puede tocar cada rol. */
export const CAPACIDAD_MODULO: Record<Capacidad, string> = {
  gestionar_academico: 'Académico',
  crear_examenes: 'Académico',
  gestionar_banco: 'Académico',
  gestionar_estructura: 'Académico',
  gestionar_notas: 'Académico',
  ver_estadisticas: 'Supervisión',
  supervisar_vivo: 'Supervisión',
  revisar_sesion: 'Supervisión',
  gestionar_usuarios: 'Sistema',
  configurar_sistema: 'Sistema',
  ver_auditoria: 'Sistema',
};

/** Orden fijo de módulos (no alfabético — de lo más frecuente/operativo a lo
 * más restringido/administrativo). */
const ORDEN_MODULOS = ['Académico', 'Supervisión', 'Sistema'] as const;

/** Lista de capacidades que tiene un rol (para mostrar sus permisos reales). */
export function capacidadesDeRol(rol: Rol): Capacidad[] {
  return (Object.keys(CAPABILITY_ROLES) as Capacidad[]).filter((c) =>
    CAPABILITY_ROLES[c].includes(rol)
  );
}

/** Capacidades de un rol, agrupadas por módulo/dominio y en el orden fijo de
 * `ORDEN_MODULOS` (para renderizar un bloque por módulo, patrón Convenios). */
export function permisosPorModuloDeRol(rol: Rol): { modulo: string; capacidades: Capacidad[] }[] {
  const propias = capacidadesDeRol(rol);
  return ORDEN_MODULOS
    .map((modulo) => ({
      modulo,
      capacidades: propias.filter((c) => CAPACIDAD_MODULO[c] === modulo),
    }))
    .filter((grupo) => grupo.capacidades.length > 0);
}
