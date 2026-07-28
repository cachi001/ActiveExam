import type { Rol } from "../types";

// Etiquetas de todos los roles reconocidos — incluye roles legacy para mostrar
// correctamente en badges y tablas si ya existen en la DB.
export const ROL_LABELS: Record<string, string> = {
  estudiante: 'Estudiante',
  docente: 'Docente',
  proctor: 'Proctor',
  admin_sistema: 'Administrador del sistema',
};

// Qué puede hacer cada rol, en castellano llano. Se muestra en el formulario de alta.
export const ROL_DESCRIPCIONES: Record<string, string> = {
  estudiante: 'Rinde exámenes. Solo ve lo suyo.',
  docente: 'Carga y configura exámenes, materias y comisiones, y cierra notas.',
  proctor: 'Supervisa exámenes en vivo y registra observaciones. No decide sanciones.',
  admin_sistema: 'Acceso total, incluida la configuración del sistema y los usuarios.',
};

// Roles que puede asignar el formulario de creación/edición de usuarios.
export const ROLES_FORMULARIO: Rol[] = ['estudiante', 'docente', 'proctor', 'admin_sistema'];

// Valores válidos para type guard en los adapters de auth.
export const ROLES_VALIDOS = Object.keys(ROL_LABELS) as Rol[];

/**
 * Retorna la etiqueta legible del rol. Si la clave no existe, retorna
 * el identificador sin transformar (fallback seguro).
 */
export function getRolLabel(rol: string): string {
  return ROL_LABELS[rol] ?? rol;
}
