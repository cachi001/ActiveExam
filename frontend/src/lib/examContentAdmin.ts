/**
 * Cliente de API admin para materia + comisión (C-69 sección 6, D11).
 *
 * Endpoints admin-only (SIN MFA, mismo guard que el import de Moodle):
 *  - POST /api/v1/exam-content/materias-comisiones  → alta inline de materia+comisión
 *    (opcionalmente asocia un examen ya importado).
 *  - POST /api/v1/exam-content/{examenId}/comision  → asocia un examen existente a
 *    una comisión existente.
 *
 * D11: la asociación examen→comisión es OPCIONAL. Un examen sin comisión sigue
 * siendo válido y rendible; esta UI/API nunca bloquea importar ni rendir.
 */

import { authProvider } from './authProvider';

export interface MateriaInline {
  codigo: string;
  nombre: string;
}

export interface ComisionInline {
  codigo: string;
  nombre: string;
  periodo?: string | null;
  anio?: number | null;
}

export interface MateriaResponse {
  id: string;
  codigo: string;
  nombre: string;
}

export interface ComisionResponse {
  id: string;
  materia_id: string;
  codigo: string;
  nombre: string;
  periodo: string | null;
  anio: number | null;
}

export interface AltaInlineResponse {
  materia: MateriaResponse;
  comision: ComisionResponse;
  examen_id: string | null;
}

export interface AsociarComisionResponse {
  examen_id: string;
  comision_id: string;
}

function authHeaders(): Record<string, string> {
  const token = authProvider.getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/**
 * Alta inline de materia + comisión. Si `examenId` viene, asocia ese examen a la
 * comisión recién creada (sin reimportar el contenido).
 */
export async function altaInlineMateriaComision(
  materia: MateriaInline,
  comision: ComisionInline,
  examenId?: string | null,
): Promise<AltaInlineResponse> {
  const res = await fetch('/api/v1/exam-content/materias-comisiones', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      materia,
      comision,
      ...(examenId ? { examen_id: examenId } : {}),
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.mensaje ?? body?.detail ?? `Error ${res.status}`);
  }
  return res.json() as Promise<AltaInlineResponse>;
}

/**
 * Asocia un examen ya importado a una comisión existente (por id).
 */
export async function asociarExamenAComision(
  examenId: string,
  comisionId: string,
): Promise<AsociarComisionResponse> {
  const res = await fetch(`/api/v1/exam-content/${examenId}/comision`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ comision_id: comisionId }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.mensaje ?? body?.detail ?? `Error ${res.status}`);
  }
  return res.json() as Promise<AsociarComisionResponse>;
}
