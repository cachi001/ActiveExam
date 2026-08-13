import type { Rol } from "../types";

// Etiquetas de todos los roles reconocidos — incluye roles legacy para mostrar
// correctamente en badges y tablas si ya existen en la DB.
export const ROL_LABELS: Record<string, string> = {
  estudiante: 'Estudiante',
  tutor: 'Tutor',
  proctor: 'Proctor',
  admin_sistema: 'Admin',
  // Legacy: cuentas viejas que todavía tuvieran el valor "docente" (pre-migración 0060).
  docente: 'Tutor',
};

// Qué puede hacer cada rol, en castellano llano. Se muestra en el formulario de alta.
export const ROL_DESCRIPCIONES: Record<string, string> = {
  estudiante: 'Rinde exámenes. Solo ve lo suyo.',
  tutor: 'Carga y configura exámenes, inscribe alumnos y cierra notas. No crea materias ni comisiones.',
  proctor: 'Supervisa exámenes en vivo y registra observaciones. No decide sanciones.',
  admin_sistema: 'Acceso total, incluida la configuración del sistema y los usuarios.',
};

// Roles que puede asignar el formulario de creación/edición de usuarios.
export const ROLES_FORMULARIO: Rol[] = ['estudiante', 'tutor', 'proctor', 'admin_sistema'];

// Valores válidos para type guard en los adapters de auth.
export const ROLES_VALIDOS = Object.keys(ROL_LABELS) as Rol[];

/**
 * Retorna la etiqueta legible del rol. Si la clave no existe, retorna
 * el identificador sin transformar (fallback seguro).
 */
export function getRolLabel(rol: string): string {
  return ROL_LABELS[rol] ?? rol;
}
