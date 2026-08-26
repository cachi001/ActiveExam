import type { Rol } from "../types";

// Etiquetas de todos los roles reconocidos — incluye roles legacy para mostrar
// correctamente en badges y tablas si ya existen en la DB.
export const ROL_LABELS: Record<string, string> = {
  estudiante: 'Estudiante',
  tutor: 'Tutor',
  profesor: 'Profesor',
  coordinador: 'Coordinador',
  admin_sistema: 'Admin',
  // Legacy: cuentas viejas que todavía tuvieran el valor "docente" (pre-migración 0060).
  docente: 'Tutor',
};

// Qué puede hacer cada rol, en castellano llano. Se muestra en el formulario de alta.
export const ROL_DESCRIPCIONES: Record<string, string> = {
  estudiante: 'Rinde exámenes. Solo ve lo suyo.',
  tutor: 'Acompaña sus comisiones: cierra notas y supervisa en vivo. NO crea exámenes, NO toca el banco de preguntas y NO administra materias, comisiones ni inscripciones.',
  profesor: 'Administra sus materias: crea comisiones, inscribe alumnos, arma los exámenes y el banco de preguntas, y supervisa en vivo. NO decide si hubo fraude: eso es del coordinador.',
  coordinador: 'Todo lo del profesor más el veredicto de integridad: es el único que puede anular una nota por fraude.',
  admin_sistema: 'Acceso total, incluida la configuración del sistema, los usuarios y la auditoría.',
};

// Roles que puede asignar el formulario de creación/edición de usuarios.
// c-76: 'proctor' y 'revisor' eliminados del dominio — el coordinador absorbe la supervisión global.
// c-76-2: 'admin_examenes' y 'auditor' eliminados del dominio — solo existe un rol "Admin".
export const ROLES_FORMULARIO: Rol[] = ['estudiante', 'tutor', 'profesor', 'coordinador', 'admin_sistema'];

// Todos los roles funcionales reconocidos por el dominio (backend/app/domain/auth/roles.py),
// para poblar selects de FILTRO (a diferencia de ROLES_FORMULARIO, que es solo lo asignable).
export const ROLES_TODOS: Rol[] = ['estudiante', 'tutor', 'profesor', 'coordinador', 'admin_sistema'];

// Valores válidos para type guard en los adapters de auth.
export const ROLES_VALIDOS = Object.keys(ROL_LABELS) as Rol[];

/**
 * Retorna la etiqueta legible del rol. Si la clave no existe, retorna
 * el identificador sin transformar (fallback seguro).
 */
export function getRolLabel(rol: string): string {
  return ROL_LABELS[rol] ?? rol;
}
