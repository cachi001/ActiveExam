// Helper puro de aviso de vencimiento de la credencial Moodle del docente (C-73 §12).
//
// La credencial vence a los 30 días desde `actualizado_en` — calculado en el
// backend (`esta_vencida`, credencial_docente_service.py), NO acá. Este helper
// solo decide qué avisarle al docente ANTES de que llegue ese momento, para que
// no lo agarre de sorpresa el día que necesita sincronizar una nota.

const DIAS_VENCIMIENTO = 30;
const DIAS_AVISO = 7;
const MS_POR_DIA = 24 * 60 * 60 * 1000;

export type AvisoConexion =
  | { tipo: 'sin_conectar' }
  | { tipo: 'ok' }
  | { tipo: 'por_vencer'; diasRestantes: number }
  | { tipo: 'vencida' }
  | { tipo: 'caida' };

export function avisoConexion(
  estado: string | null,
  actualizadoEn: string | null,
  ahora: Date = new Date(),
): AvisoConexion {
  if (!estado) return { tipo: 'sin_conectar' };
  if (estado === 'caida') return { tipo: 'caida' };
  if (estado === 'vencida') return { tipo: 'vencida' };
  if (estado !== 'activa' || !actualizadoEn) return { tipo: 'ok' };

  const dias = Math.floor((ahora.getTime() - new Date(actualizadoEn).getTime()) / MS_POR_DIA);
  const diasRestantes = DIAS_VENCIMIENTO - dias;
  if (diasRestantes <= DIAS_AVISO) {
    return { tipo: 'por_vencer', diasRestantes: Math.max(diasRestantes, 0) };
  }
  return { tipo: 'ok' };
}
