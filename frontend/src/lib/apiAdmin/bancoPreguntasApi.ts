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

import { fetchAutenticado } from '../fetchAutenticado';
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
  /**
   * true si el tutor la movió de categoría a mano. Ni el import de XML ni el
   * sync desde Moodle vuelven a recategorizarla (0058).
   */
  categoria_manual: boolean;
}

function headers() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${authProvider.getToken()}`,
  };
}

export async function listarCategorias(materiaId: string): Promise<CategoriaPregunta[]> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/categorias?materia_id=${encodeURIComponent(materiaId)}`,
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
  const res = await fetchAutenticado(`${API_BASE}/exam-content/categorias`, {
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
  const res = await fetchAutenticado(`${API_BASE}/exam-content/categorias/${encodeURIComponent(categoriaId)}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify({ nombre }),
  });
  if (!res.ok) throw new Error(`Error ${res.status} al renombrar categoría`);
  return res.json();
}

/**
 * Re-anida una categoría bajo otra (o a raíz si `nuevoPadreId` es null).
 * PATCH /exam-content/categorias/:id con { categoria_padre_id }.
 * 409 → ciclo (moverla dentro de sí misma o de una subcategoría suya) o materia distinta.
 */
export async function moverCategoria(
  categoriaId: string,
  nuevoPadreId: string | null,
): Promise<CategoriaPregunta> {
  const res = await fetchAutenticado(`${API_BASE}/exam-content/categorias/${encodeURIComponent(categoriaId)}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify({ categoria_padre_id: nuevoPadreId }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = (body as any)?.detail;
    const msg =
      typeof detail === 'string' ? detail : detail?.mensaje ?? `Error ${res.status} al mover categoría`;
    throw new Error(msg);
  }
  return res.json();
}

export async function borrarCategoria(categoriaId: string): Promise<void> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/categorias/${encodeURIComponent(categoriaId)}`,
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
  const res = await fetchAutenticado(`${API_BASE}/exam-content/preguntas?${params}`, {
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Error ${res.status} al listar preguntas`);
  return res.json();
}

export async function moverPreguntaCategoria(
  preguntaId: string,
  categoriaId: string | null,
): Promise<void> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/preguntas/${encodeURIComponent(preguntaId)}/categoria`,
    {
      method: 'PATCH',
      headers: headers(),
      body: JSON.stringify({ categoria_id: categoriaId }),
    },
  );
  if (!res.ok) throw new Error(`Error ${res.status} al mover pregunta`);
}

export interface SorteoCategoriaItem {
  categoria_id: string | null;
  cantidad: number;
  tipos?: string[] | null;
}

export interface CrearDesdebancoRequest {
  titulo: string;
  materia_id: string;
  comision_id?: string | null;
  sorteo: SorteoCategoriaItem[];
  limite_preguntas?: number | null;
  /** Escala de calificación del examen. Default 100/60 si se omite (nunca "sobre 10"). */
  nota_maxima?: number;
  nota_aprobacion?: number;
}

export interface CrearDesdebancoResponse {
  examen_id: string;
  titulo: string;
  total_preguntas: number;
}

export async function crearDesdeBanco(
  payload: CrearDesdebancoRequest,
): Promise<CrearDesdebancoResponse> {
  const res = await fetchAutenticado(`${API_BASE}/exam-content/crear-desde-banco`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = (body as any)?.detail;
    const msg =
      typeof detail === 'string'
        ? detail
        : detail?.mensaje ?? `Error ${res.status} al crear examen`;
    throw new Error(msg);
  }
  return res.json();
}

export interface OmitidaItem {
  tipo: string;
  nombre: string;
  motivo: string;
}

export interface PreguntaImportadaItem {
  enunciado: string;
  tipo: string;
}

export interface ImportarBancoXmlResult {
  preguntas_nuevas: number;
  preguntas_actualizadas: number;
  omitidas: OmitidaItem[];
  nuevas: PreguntaImportadaItem[];
  actualizadas: PreguntaImportadaItem[];
}

/**
 * Importa un XML de Moodle directo al banco de preguntas de una materia.
 * NO crea ningún examen — el banco es el destino. El examen se arma después,
 * por separado, sorteando categorías/tipos desde acá (crearDesdeBanco).
 * POST /api/v1/exam-content/banco/importar-xml
 */
export async function importarBancoXml(
  materiaId: string,
  file: File,
  categoriasExcluidas?: string[][],
  categoriaPadreId?: string | null,
): Promise<ImportarBancoXmlResult> {
  const formData = new FormData();
  formData.append('materia_id', materiaId);
  formData.append('file', file);
  if (categoriasExcluidas && categoriasExcluidas.length > 0) {
    formData.append('categorias_excluidas', JSON.stringify(categoriasExcluidas));
  }
  // Bug real (2026-08-21, campus FRM): Moodle nunca exporta una categoría
  // propia para el nodo "top" — las subcategorías quedaban sueltas sin padre
  // común. categoria_padre_id (una categoría YA EXISTENTE elegida en un
  // selector, no tipeada) anida todo el XML ahí.
  if (categoriaPadreId) {
    formData.append('categoria_padre_id', categoriaPadreId);
  }

  const res = await fetchAutenticado(`${API_BASE}/exam-content/banco/importar-xml`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${authProvider.getToken()}` },
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = (body as any)?.detail;
    const msg =
      typeof detail === 'string'
        ? detail
        : detail?.mensaje ?? `Error ${res.status} al importar`;
    throw new Error(msg);
  }
  return res.json();
}

export interface PreviewCategoria {
  ruta: string[];
  preguntas_por_tipo: Record<string, number>;
  preguntas: PreguntaImportadaItem[];
}

export interface PreviewImportBancoResult {
  categorias: PreviewCategoria[];
  sin_categoria_por_tipo: Record<string, number>;
  omitidas: OmitidaItem[];
  total_preguntas: number;
  sin_categoria_preguntas: PreguntaImportadaItem[];
}

/**
 * Preview de un XML antes de importarlo: árbol de categorías + conteo por
 * tipo. NO persiste nada — solo parsea, para mostrarle al docente qué va a
 * entrar al banco antes de confirmar.
 * POST /api/v1/exam-content/banco/importar-xml/preview
 */
export async function previewImportarBancoXml(file: File): Promise<PreviewImportBancoResult> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetchAutenticado(`${API_BASE}/exam-content/banco/importar-xml/preview`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${authProvider.getToken()}` },
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = (body as any)?.detail;
    const msg =
      typeof detail === 'string'
        ? detail
        : detail?.mensaje ?? `Error ${res.status} al previsualizar`;
    throw new Error(msg);
  }
  return res.json();
}

