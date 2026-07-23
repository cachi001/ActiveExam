import type { Rol } from "../types";

// Etiquetas de los roles en español. Fuente canónica para TODA la UI
// (formularios, tablas, cards, filtros).
//
// Esta lista debe cubrir el enum `Rol` del backend COMPLETO. Cuando declaraba
// solo tres, los otros roles no se podían asignar desde el alta de usuarios: el
// rol `revisor` era imposible de crear y, como es el único con la capacidad
// `resolver_caso`, nadie podía anular un examen por fraude.
//
// El orden es el de menor a mayor alcance — así se lee en el formulario.
export const ROL_LABELS: Record<string, string> = {
  estudiante: 'Estudiante',
  docente: 'Docente',
  proctor: 'Proctor',
  revisor: 'Revisor',
  coordinador: 'Coordinador',
  admin_examenes: 'Administrador de exámenes',
  auditor: 'Auditor',
  admin_sistema: 'Administrador del sistema',
};

// Qué puede hacer cada rol, en castellano llano. Se muestra junto a la opción en
// el alta: elegir un rol es una decisión de permisos y quien la toma tiene que
// ver la consecuencia sin leer el código.
export const ROL_DESCRIPCIONES: Record<string, string> = {
  estudiante: 'Rinde exámenes. Solo ve lo suyo.',
  docente: 'Carga y configura exámenes, materias y comisiones, y cierra notas. No supervisa ni revisa sesiones.',
  proctor: 'Supervisa exámenes en vivo y registra observaciones. No decide sanciones.',
  revisor: 'Revisa las sesiones marcadas y decide: aprobar la nota o anular por fraude.',
  coordinador: 'Gestión académica y revisión de sesiones de su jurisdicción.',
  admin_examenes: 'Administra todos los exámenes, materias y comisiones.',
  auditor: 'Solo lectura del registro de auditoría. No opera el sistema.',
  admin_sistema: 'Acceso total, incluida la configuración del sistema y los usuarios.',
};

// Valores válidos. Tipado como Rol[] para que los adapters de auth puedan usarlo
// como type guard al filtrar los roles del token sin castear a ciegas.
export const ROLES_VALIDOS = Object.keys(ROL_LABELS) as Rol[];

/**
 * Retorna la etiqueta legible del rol. Si la clave no existe, retorna
 * el identificador sin transformar (fallback seguro).
 */
export function getRolLabel(rol: string): string {
  return ROL_LABELS[rol] ?? rol;
}
