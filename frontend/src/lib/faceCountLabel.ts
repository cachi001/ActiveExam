/**
 * faceCountLabel — helper compartido de fraseo humano del conteo de rostros (C-53).
 *
 * Fuente ÚNICA de la lógica de pluralización del conteo de rostros (`face_count`)
 * para todas las superficies de UI: panel de señales, card de evento y log.
 * Evita números crudos (`srv:2`) y prefijos técnicos, y centraliza la
 * pluralización para que no diverja entre archivos (D5 del design C-53).
 */

/**
 * Fraseo humano de un conteo de rostros con pluralización correcta.
 *
 *   0  → "sin rostros"
 *   1  → "1 rostro detectado"
 *   N  → "N rostros detectados"
 *
 * `null`/`undefined` → "—" (sin dato).
 */
export function formatRostros(n: number | null | undefined): string {
  if (n == null) return '—';
  if (n === 0) return 'sin rostros';
  if (n === 1) return '1 rostro detectado';
  return `${n} rostros detectados`;
}

/**
 * Fraseo humano de un conteo de rostros rotulado por su origen (cliente/servidor).
 *
 *   formatRostrosConOrigen('Servidor', 2) → "Servidor: 2 rostros"
 *   formatRostrosConOrigen('Cliente', 1)  → "Cliente: 1 rostro"
 *   formatRostrosConOrigen('Servidor', 0) → "Servidor: sin rostros"
 *
 * `null`/`undefined` → "{origen}: —".
 */
export function formatRostrosConOrigen(
  origen: 'Cliente' | 'Servidor',
  n: number | null | undefined,
): string {
  if (n == null) return `${origen}: —`;
  if (n === 0) return `${origen}: sin rostros`;
  if (n === 1) return `${origen}: 1 rostro`;
  return `${origen}: ${n} rostros`;
}
