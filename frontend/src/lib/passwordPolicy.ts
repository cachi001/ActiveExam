/**
 * Política de contraseñas del frontend — espeja `backend/app/domain/auth/password_policy.py`.
 *
 * Nivel Media: mínimo 8 caracteres, con al menos una mayúscula, una minúscula y
 * un dígito. Valida en cliente para dar feedback inmediato; el backend vuelve a
 * validar (nunca se confía en el cliente).
 */

export const LONGITUD_MINIMA_PASSWORD = 8;

export const REQUISITOS_PASSWORD = 'Mínimo 8 caracteres, con una mayúscula, una minúscula y un número.';

/**
 * Devuelve un mensaje con los requisitos faltantes, o `null` si la contraseña
 * cumple la política.
 */
export function validarPasswordFuerte(password: string): string | null {
  const faltantes: string[] = [];
  if (password.length < LONGITUD_MINIMA_PASSWORD) faltantes.push(`al menos ${LONGITUD_MINIMA_PASSWORD} caracteres`);
  if (!/[A-Z]/.test(password)) faltantes.push('una letra mayúscula');
  if (!/[a-z]/.test(password)) faltantes.push('una letra minúscula');
  if (!/[0-9]/.test(password)) faltantes.push('un número');
  if (faltantes.length === 0) return null;
  return 'La contraseña debe tener ' + faltantes.join(', ') + '.';
}
