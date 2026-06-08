// Etiquetas de los tres roles del MVP en español.
// Fuente canónica: usar esta constante en toda la UI (formularios, tablas, cards).

export const ROL_LABELS: Record<string, string> = {
  estudiante: 'Estudiante',
  proctor: 'Proctor',
  admin_sistema: 'Administrador del sistema',
};

// Valores válidos del MVP — mismos que ROLES_VALIDOS en GestionUsuarios.
export const ROLES_VALIDOS = Object.keys(ROL_LABELS);

/**
 * Retorna la etiqueta legible del rol. Si la clave no existe, retorna
 * el identificador sin transformar (fallback seguro).
 */
export function getRolLabel(rol: string): string {
  return ROL_LABELS[rol] ?? rol;
}
