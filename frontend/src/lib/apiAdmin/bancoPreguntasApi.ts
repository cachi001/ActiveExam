/**
 * Cliente de API para el banco de preguntas categorizado (C-74 §4).
 *
 * Endpoints:
 *  GET  /api/v1/exam-content/categorias?materia_id=  → árbol de categorías
 *  POST /api/v1/exam-content/categorias               → crear categoría
 *  PATCH /api/v1/exam-content/categorias/:id          → renombrar categoría
 *  DELETE /api/v1/exam-content/categorias/:id         → borrar categoría
 *  GET  /api/v1/exam-content/preguntas?materia_id=&categoria_id=  → listar preguntas del banco
 *  PATCH /api/v1/exam-content/preguntas/:id/categoria → mover pregunta a categoría
 */

import { authProvider } from '../authProvider';
import { API_BASE } from '../api';

export interface CategoriaPregunta {
  id: string;
  nombre: string;
  materia_id: string;
  categoria_padre_id: string | null;
  creada_en: string;
}

export interface PreguntaBanco {
  id: string;
  enunciado: string;
  tipo: string;
  orden: number;
  seleccionada: boolean;
  categoria_id: string | null;
}

function headers() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${authProvider.getToken()}`,
  };
}

export async function listarCategorias(materiaId: string): Promise<CategoriaPregunta[]> {
  const res = await fetch(
    `${API_BASE}/api/v1/exam-content/categorias?materia_id=${encodeURIComponent(materiaId)}`,
    { headers: headers() },
  );
  if (!res.ok) throw new Error(`Error ${res.status} al listar categorías`);
  return res.json();
}

export async function crearCategoria(payload: {
  materia_id: string;
  nombre: string;
  categoria_padre_id?: string | null;
}): Promise<CategoriaPregunta> {
  const res = await fetch(`${API_BASE}/api/v1/exam-content/categorias`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Error ${res.status} al crear categoría`);
  return res.json();
}

export async function renombrarCategoria(
  categoriaId: string,
  nombre: string,
): Promise<CategoriaPregunta> {
  const res = await fetch(`${API_BASE}/api/v1/exam-content/categorias/${encodeURIComponent(categoriaId)}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify({ nombre }),
  });
  if (!res.ok) throw new Error(`Error ${res.status} al renombrar categoría`);
  return res.json();
}

export async function borrarCategoria(categoriaId: string): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/v1/exam-content/categorias/${encodeURIComponent(categoriaId)}`,
    { method: 'DELETE', headers: headers() },
  );
  if (!res.ok) throw new Error(`Error ${res.status} al borrar categoría`);
}

export async function listarPreguntasBanco(
  materiaId: string,
  categoriaId: string | null,
): Promise<PreguntaBanco[]> {
  const params = new URLSearchParams({ materia_id: materiaId });
  if (categoriaId) params.set('categoria_id', categoriaId);
  else params.set('sin_categoria', 'true');
  const res = await fetch(`${API_BASE}/api/v1/exam-content/preguntas?${params}`, {
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Error ${res.status} al listar preguntas`);
  return res.json();
}

export async function moverPreguntaCategoria(
  preguntaId: string,
  categoriaId: string | null,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/v1/exam-content/preguntas/${encodeURIComponent(preguntaId)}/categoria`,
    {
      method: 'PATCH',
      headers: headers(),
      body: JSON.stringify({ categoria_id: categoriaId }),
    },
  );
  if (!res.ok) throw new Error(`Error ${res.status} al mover pregunta`);
}

export interface SyncBancoResult {
  categorias_creadas: number;
  preguntas_nuevas: number;
  preguntas_actualizadas: number;
}

/**
 * Sincroniza el banco de preguntas de una materia desde el campus Moodle.
 * POST /api/v1/exam-content/moodle/sync-banco
 */
export async function sincronizarBancoMoodle(
  materiaId: string,
  courseid: number,
): Promise<SyncBancoResult> {
  const res = await fetch(`${API_BASE}/api/v1/exam-content/moodle/sync-banco`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ materia_id: materiaId, courseid }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = (body as any)?.detail;
    throw new Error(
      typeof detail === 'string' ? detail : detail?.mensaje ?? `Error ${res.status} al sincronizar`,
    );
  }
  return res.json() as Promise<SyncBancoResult>;
}
