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
/** Filtro de baja lógica: vigentes, la papelera, o ambas. */
export type EstadoPregunta = 'activa' | 'eliminada' | 'todas';

export interface CategoriaPregunta {
  id: string;
  nombre: string;
  materia_id: string;
  categoria_padre_id: string | null;
  creada_en: string;
  /**
   * Baja lógica. null = vigente; con fecha ISO = dada de baja junto con toda su
   * rama. Las preguntas conservan su categoría y todo se puede reactivar.
   */
  eliminada_en?: string | null;
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
  /**
   * Baja lógica. null = vigente; con fecha ISO = dada de baja (sale del banco y
   * de los exámenes que se armen desde ahora, pero no se borra y se reactiva).
   */
  eliminada_en?: string | null;
}

function headers() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${authProvider.getToken()}`,
  };
}

export async function listarCategorias(
  materiaId: string,
  estado: EstadoPregunta = 'activa',
): Promise<CategoriaPregunta[]> {
  const params = new URLSearchParams({ materia_id: materiaId, estado });
  const res = await fetchAutenticado(`${API_BASE}/exam-content/categorias?${params}`, {
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Error ${res.status} al listar categorías`);
  return res.json();
}

/** Devuelve al árbol una categoría dada de baja, con toda su rama. */
export async function reactivarCategoria(categoriaId: string): Promise<void> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/categorias/${encodeURIComponent(categoriaId)}/reactivar`,
    { method: 'POST', headers: headers() },
  );
  if (!res.ok) throw new Error(`Error ${res.status} al reactivar la categoría`);
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
  /** id de categoría; `null` = solo las sin clasificar; omitido = TODAS las de la
   *  materia, cada una con su `categoria_id`. Esta última forma es la que usa el
   *  armado del sorteo para contar por rama sin hacer una request por categoría. */
  categoriaId?: string | null,
  estado: EstadoPregunta = 'activa',
): Promise<PreguntaBanco[]> {
  const params = new URLSearchParams({ materia_id: materiaId, estado });
  if (categoriaId) params.set('categoria_id', categoriaId);
  else if (categoriaId === null) params.set('sin_categoria', 'true');
  const res = await fetchAutenticado(`${API_BASE}/exam-content/preguntas?${params}`, {
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Error ${res.status} al listar preguntas`);
  return res.json();
}

/**
 * Da de baja una pregunta del banco. Baja LÓGICA: no se borra y se puede
 * reactivar. Lanza con el mensaje del backend si la pregunta está en el pool de
 * un examen vigente (409), donde se seguiría sorteando.
 */
export async function darDeBajaPregunta(preguntaId: string): Promise<void> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/preguntas/${encodeURIComponent(preguntaId)}`,
    { method: 'DELETE', headers: headers() },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = (body as any)?.detail;
    const msg =
      typeof detail === 'string'
        ? detail
        : detail?.mensaje ?? `Error ${res.status} al dar de baja la pregunta`;
    throw new Error(msg);
  }
}

/** Devuelve al banco una pregunta dada de baja. */
export async function reactivarPregunta(preguntaId: string): Promise<void> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/preguntas/${encodeURIComponent(preguntaId)}/reactivar`,
    { method: 'POST', headers: headers() },
  );
  if (!res.ok) throw new Error(`Error ${res.status} al reactivar la pregunta`);
}

export interface OpcionPreview {
  texto: string;
  orden: number;
  es_correcta: boolean;
}

export interface BlankPreview {
  orden: number;
  tipo: string;
  texto_antes: string | null;
  texto_despues: string | null;
  opciones: OpcionPreview[];
}

/** Una pregunta del banco tal como la va a ver el alumno (c-78 E-08, 15.3). */
export interface PreguntaPreview {
  id: string;
  enunciado: string;
  tipo: string;
  opciones: OpcionPreview[];
  blanks: BlankPreview[];
}

export async function previewPreguntaBanco(
  preguntaId: string,
): Promise<PreguntaPreview> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/preguntas/${encodeURIComponent(preguntaId)}/preview`,
    { headers: headers() },
  );
  if (!res.ok) throw new Error(`No se pudo cargar la vista previa (HTTP ${res.status}).`);
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
  /**
   * Si el pool del tramo es la categoría sola o toda su descendencia. El backend
   * lo tiene en `true` por default, así que omitirlo sorteaba sobre la rama
   * entera sin que la UI lo dijera ni lo mostrara en los conteos.
   */
  incluir_subcategorias?: boolean;
}

export interface CrearDesdebancoRequest {
  titulo: string;
  materia_id: string;
  comision_id?: string | null;
  /**
   * c-78 E-06: crea el mismo examen para varias comisiones de la materia. Se
   * sortea una sola vez y ese set se copia a N exámenes independientes, en una
   * operación todo o nada. Excluyente con `comision_id`.
   */
  comision_ids?: string[] | null;
  /**
   * c-78 E-07: cada alumno recibe preguntas distintas, sorteadas al arrancar su
   * intento. El examen se lleva el POOL entero de cada tramo (no solo las que se
   * sortean) y guarda la regla, así el sorteo posterior no depende del banco.
   */
  sorteo_por_intento?: boolean;
  /** c-78 E-07: nace invisible para el alumno, para poder probarlo antes. */
  borrador?: boolean;
  sorteo: SorteoCategoriaItem[];
  /**
   * De qué preguntas del banco puede salir el sorteo. Se manda solo cuando el
   * docente destildó alguna: sin esto, el pool es todo lo que califique por
   * categoría y tipo.
   */
  pool_preguntas?: string[];
  limite_preguntas?: number | null;
  /** Escala de calificación del examen. Default 100/60 si se omite (nunca "sobre 10"). */
  nota_maxima?: number;
  nota_aprobacion?: number;
}

export interface ExamenReplicaItem {
  examen_id: string;
  comision_id: string | null;
  titulo: string;
}

export interface CrearDesdebancoResponse {
  /** El primer examen creado. Con una sola comisión, el único. */
  examen_id: string;
  titulo: string;
  total_preguntas: number;
  /** Todos los exámenes creados, en el orden en que se pidieron las comisiones. */
  examenes: ExamenReplicaItem[];
  /** Marca compartida por las réplicas. null cuando se creó un examen solo. */
  lote_replica_id: string | null;
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

