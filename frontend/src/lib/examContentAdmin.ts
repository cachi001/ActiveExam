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
import { fetchAutenticado } from './fetchAutenticado';
import { API_BASE } from './api';
import type { AlumnoInscripto } from './types';

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
  activa?: boolean;
}

export interface ComisionResponse {
  id: string;
  materia_id: string;
  codigo: string;
  nombre: string;
  periodo: string | null;
  anio: number | null;
  // C-70: código de matriculación (enrolment key) que el tutor comparte.
  codigo_matriculacion: string;
  // C-72 §17: true = activa; false = desactivada (baja lógica).
  activa?: boolean;
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

/** Destino de la nota en Moodle para un examen (curso + actividad/cmid). */
export interface MoodleTarget {
  moodle_courseid: number | null;
  moodle_cmid: number | null;
}

export interface MoodleTargetResponse extends MoodleTarget {
  examen_id: string;
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
  const res = await fetchAutenticado(`${API_BASE}/exam-content/materias-comisiones`, {
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
  const res = await fetchAutenticado(`${API_BASE}/exam-content/${examenId}/comision`, {
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

// ---------------------------------------------------------------------------
// C-69: CRUD de materias y comisiones (admin-only).
// Endpoints bajo /api/v1/exam-content/ (mismo guard Bearer que el resto).
// Manejo de error unificado: el objeto Error lleva `.status` HTTP para que
// el llamador distinga 409 (duplicado) / 422 (validación) / 404 (no existe).
// ---------------------------------------------------------------------------

/** Construye y lanza un error tipado con `.status` a partir de la respuesta HTTP. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function throwAdminError(res: Response): Promise<never> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const body: any = await res.json().catch(() => ({}));
  const msg: string =
    body?.error ??
    body?.detail?.mensaje ??
    body?.detail ??
    `Error ${res.status}`;
  const err = Object.assign(new Error(msg), { status: res.status });
  throw err;
}

/** Crea una materia nueva. Admin-only. POST /exam-content/materias.
 *  409 → duplicado  |  422 → validacion_dominio. */
export async function crearMateria(data: {
  codigo: string;
  nombre: string;
}): Promise<MateriaResponse> {
  const res = await fetchAutenticado(`${API_BASE}/exam-content/materias`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) return throwAdminError(res);
  return res.json() as Promise<MateriaResponse>;
}

/** Actualiza una materia existente (nombre y/o código). Admin-only.
 *  PATCH /exam-content/materias/{materiaId}.  404 → no existe  |  409 → código
 *  duplicado (si se edita el código a uno ya en uso). */
export async function actualizarMateria(
  materiaId: string,
  data: { nombre: string; codigo?: string },
): Promise<MateriaResponse> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/materias/${encodeURIComponent(materiaId)}`,
    {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(data),
    },
  );
  if (!res.ok) return throwAdminError(res);
  return res.json() as Promise<MateriaResponse>;
}

/**
 * Qué se lleva puesto una baja (c-78, Opción C). Es una CONSULTA: pedirla no da
 * de baja nada. La pantalla la usa para avisar, antes de confirmar, cuántas
 * rendiciones tiene lo que se está por dar de baja.
 *
 * `sesiones_en_curso > 0` es lo único que bloquea: ahí el DELETE responde 409.
 * `rendiciones` nunca bloquea — su evidencia se conserva igual.
 */
export interface ImpactoBaja {
  sesiones_en_curso: number;
  rendiciones: number;
  examenes: number;
  comisiones: number;
}

async function pedirImpacto(ruta: string): Promise<ImpactoBaja> {
  const res = await fetchAutenticado(`${API_BASE}/exam-content/${ruta}/impacto-baja`, {
    headers: authHeaders(),
  });
  if (!res.ok) return throwAdminError(res);
  return res.json() as Promise<ImpactoBaja>;
}

export function impactoBajaMateria(materiaId: string): Promise<ImpactoBaja> {
  return pedirImpacto(`materias/${encodeURIComponent(materiaId)}`);
}

export function impactoBajaComision(comisionId: string): Promise<ImpactoBaja> {
  return pedirImpacto(`comisiones/${encodeURIComponent(comisionId)}`);
}

export function impactoBajaExamen(examenId: string): Promise<ImpactoBaja> {
  return pedirImpacto(encodeURIComponent(examenId));
}

/**
 * Baja lógica de una materia (c-78). UN SOLO patrón en todo el sistema:
 * `DELETE /{id}` da de baja, `POST /{id}/reactivar` la revierte. Igual que
 * usuario y examen.
 *
 * NADA se borra: comisiones, inscripciones, exámenes y evidencia quedan. El
 * borrado físico (que antes hacía este mismo DELETE si la materia estaba vacía)
 * se eliminó: un DELETE que a veces borra y a veces devuelve 409 según el
 * contenido de la fila es un contrato impredecible.
 *
 * 204 → dada de baja  |  404 → no existe o ya estaba de baja.
 */
export async function darDeBajaMateria(materiaId: string): Promise<void> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/materias/${encodeURIComponent(materiaId)}`,
    { method: 'DELETE', headers: authHeaders() },
  );
  if (!res.ok) await throwAdminError(res);
}

/** Revierte la baja de una materia. POST /exam-content/materias/{id}/reactivar.
 *  404 → no existe o ya estaba activa. */
export async function reactivarMateria(materiaId: string): Promise<MateriaResponse> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/materias/${encodeURIComponent(materiaId)}/reactivar`,
    { method: 'POST', headers: authHeaders() },
  );
  if (!res.ok) return throwAdminError(res);
  return res.json() as Promise<MateriaResponse>;
}

/** Baja lógica de una comisión (c-78, mismo patrón que materia/usuario/examen).
 *  No desmatricula a nadie ni borra nada.
 *  204 → dada de baja  |  404 → no existe o ya estaba de baja. */
export async function darDeBajaComision(comisionId: string): Promise<void> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/comisiones/${encodeURIComponent(comisionId)}`,
    { method: 'DELETE', headers: authHeaders() },
  );
  if (!res.ok) await throwAdminError(res);
}

/** Revierte la baja de una comisión. POST /exam-content/comisiones/{id}/reactivar. */
export async function reactivarComision(comisionId: string): Promise<ComisionResponse> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/comisiones/${encodeURIComponent(comisionId)}/reactivar`,
    { method: 'POST', headers: authHeaders() },
  );
  if (!res.ok) return throwAdminError(res);
  return res.json() as Promise<ComisionResponse>;
}

/** Crea una comisión bajo una materia. Admin-only.
 *  POST /exam-content/materias/{materiaId}/comisiones.
 *  404 → materia no existe  |  409 → duplicado  |  422 → validacion_dominio. */
export async function crearComision(
  materiaId: string,
  data: {
    codigo: string;
    nombre: string;
    periodo?: string | null;
    anio?: number | null;
    // C-70: opcional. Si se omite/vacía, el backend autogenera uno único.
    codigo_matriculacion?: string | null;
  },
): Promise<ComisionResponse> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/materias/${encodeURIComponent(materiaId)}/comisiones`,
    {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    },
  );
  if (!res.ok) return throwAdminError(res);
  return res.json() as Promise<ComisionResponse>;
}

/** Actualiza una comisión existente. Admin-only.
 *  PATCH /exam-content/comisiones/{comisionId}.  404 → no existe. */
export async function actualizarComision(
  comisionId: string,
  data: {
    nombre: string;
    periodo?: string | null;
    anio?: number | null;
    // C-70: opcional. Si viene (no vacío), fija/edita el código (unicidad → 409).
    codigo_matriculacion?: string | null;
  },
): Promise<ComisionResponse> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/comisiones/${encodeURIComponent(comisionId)}`,
    {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(data),
    },
  );
  if (!res.ok) return throwAdminError(res);
  return res.json() as Promise<ComisionResponse>;
}

/** Rota (regenera) el código de matriculación de una comisión. Admin-only.
 *  POST /exam-content/comisiones/{comisionId}/rotar-codigo.  404 → no existe.
 *  Las inscripciones existentes NO se tocan. */
export async function rotarCodigoMatriculacion(
  comisionId: string,
): Promise<ComisionResponse> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/comisiones/${encodeURIComponent(comisionId)}/rotar-codigo`,
    {
      method: 'POST',
      headers: authHeaders(),
    },
  );
  if (!res.ok) return throwAdminError(res);
  return res.json() as Promise<ComisionResponse>;
}

/**
 * Define (o reemplaza) el destino de la nota en Moodle para un examen ya
 * importado: a qué curso (courseid) y actividad/calificación (cmid) se le
 * devolverá la nota. Ambos pueden ser null para limpiar el destino.
 */
export async function setMoodleTarget(
  examenId: string,
  target: MoodleTarget,
): Promise<MoodleTargetResponse> {
  const res = await fetchAutenticado(`${API_BASE}/exam-content/${examenId}/moodle-target`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(target),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.mensaje ?? body?.detail ?? `Error ${res.status}`);
  }
  return res.json() as Promise<MoodleTargetResponse>;
}

/**
 * Convierte el valor de un input de courseid/cmid (texto) a `number | null`.
 * Vacío (o solo espacios) → null (limpia el destino → cae al global). Un valor
 * no numérico también cae a null para no enviar basura al backend.
 */
export function parseMoodleId(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === '') return null;
  const n = Number(trimmed);
  return Number.isFinite(n) ? n : null;
}

/**
 * Arma un `MoodleTarget` a partir de los dos inputs de la UI (courseid + cmid).
 * Ambos vacíos → destino limpio (null/null) = fallback al destino global.
 */
export function buildMoodleTarget(courseIdInput: string, cmidInput: string): MoodleTarget {
  return {
    moodle_courseid: parseMoodleId(courseIdInput),
    moodle_cmid: parseMoodleId(cmidInput),
  };
}

/** Lee el destino de la nota en Moodle de un examen importado. */
export async function getMoodleTarget(examenId: string): Promise<MoodleTargetResponse> {
  const res = await fetchAutenticado(`${API_BASE}/exam-content/${examenId}/moodle-target`, {
    method: 'GET',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.mensaje ?? body?.detail ?? `Error ${res.status}`);
  }
  return res.json() as Promise<MoodleTargetResponse>;
}

// ---------------------------------------------------------------------------
// Configuración del examen: el tutor la define, la plataforma la aplica.
// GET/PATCH /api/v1/exam-content/{id}/config — las validaciones finales son
// server-side; el cliente sólo valida lo básico para feedback inmediato.
// ---------------------------------------------------------------------------

/** Configuración de un examen (la define el tutor; la aplica la plataforma). */
export interface ExamConfig {
  /** Minutos de tiempo límite. null = sin límite (no hay cuenta regresiva). */
  tiempo_limite_min: number | null;
  /** Intentos permitidos por alumno (mín 1). */
  intentos_permitidos: number;
  /** ISO 8601 de apertura de la ventana de rendición. null = sin restricción. */
  apertura: string | null;
  /** ISO 8601 de cierre de la ventana de rendición. null = sin restricción. */
  cierre: string | null;
  /** Nota máxima de la escala (ej. 10 o 100). */
  nota_maxima: number;
  /** Nota mínima para aprobar (debe ser ≤ nota_maxima). */
  nota_aprobacion: number;
  /** Siempre true: el orden aleatorio por alumno es obligatorio (no editable). Se
   *  expone para poder informarlo en la UI. */
  mezclar_preguntas: boolean;
  /** Tope de preguntas del examen. null = sin tope. Al escribirlo, 0 = sacar el tope. */
  limite_preguntas: number | null;
  /**
   * Cuándo se muestra la nota al alumno.
   * - 'nunca' (default de todo examen nuevo, c-78 D9): oculta hasta que alguien
   *   la publique explícitamente.
   * - 'al_cerrar': visible después de la fecha de cierre.
   * - 'inmediata': visible al entregar.
   *
   * Solo avanza: nunca → al_cerrar → inmediata. Volver atrás lo rechaza el backend.
   */
  mostrar_nota: MostrarNota;
  /** c-78 D9: cuándo se publicaron las notas (ISO). null = todavía ocultas. */
  notas_publicadas_en?: string | null;
  /** c-78 D9: quién las publicó. null = todavía ocultas. */
  notas_publicadas_por?: string | null;
  /** c-78 D10: si el alumno ve sus eventos de proctoring mientras rinde. Default no. */
  mostrar_eventos_alumno?: boolean;
  /** C-69: si el alumno puede revisar la corrección (respuestas correctas). Solo se
   *  muestra después del cierre. */
  revision_habilitada: boolean;
  /** C-73: qué nota se envía a Moodle cuando hay múltiples intentos. */
  politica_intentos: 'mas_alta' | 'ultimo' | 'primero' | 'manual';
  /** True si el examen ya tiene >= 1 intento finalizado: la config de
   *  mecánica/nota queda CONGELADA (el editor deshabilita esos campos). Solo se
   *  puede cambiar la publicación de resultados. */
  bloqueada?: boolean;
}

/**
 * Valores de visibilidad de la nota, en orden CRECIENTE de exposición (c-78 D9).
 * El índice en este array ES el "cuánto se ve": publicar solo avanza.
 */
export const ORDEN_MOSTRAR_NOTA = ['nunca', 'al_cerrar', 'inmediata'] as const;
export type MostrarNota = (typeof ORDEN_MOSTRAR_NOTA)[number];

/** true si `actual` puede pasar a `nuevo` (espeja la regla del backend). */
export function puedeAvanzarVisibilidad(actual: MostrarNota, nuevo: MostrarNota): boolean {
  return ORDEN_MOSTRAR_NOTA.indexOf(nuevo) >= ORDEN_MOSTRAR_NOTA.indexOf(actual);
}

/**
 * Publica las notas del examen (c-78 D9). Es CAMINO DE IDA: un examen ya
 * publicado responde 409, y no hay forma de volver a ocultarlas.
 * POST /exam-content/{id}/publicar-notas
 */
export async function publicarNotasExamen(examenId: string): Promise<ExamConfig> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/${examenId}/publicar-notas`,
    { method: 'POST', headers: authHeaders() },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detalle = (body as { detail?: { mensaje?: string } })?.detail?.mensaje;
    throw new Error(detalle ?? `No se pudieron publicar las notas (HTTP ${res.status}).`);
  }
  return (await res.json()) as ExamConfig;
}

/** Lee la configuración del examen. Admin-only. GET /exam-content/{id}/config */
export async function getExamConfig(examenId: string): Promise<ExamConfig> {
  const res = await fetchAutenticado(`${API_BASE}/exam-content/${examenId}/config`, {
    method: 'GET',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.mensaje ?? body?.detail ?? `Error ${res.status}`);
  }
  return res.json() as Promise<ExamConfig>;
}

/**
 * Actualiza (parcialmente) la configuración del examen. Admin-only.
 * PATCH /exam-content/{id}/config — acepta un subconjunto de campos.
 * Las validaciones definitivas (aprobación ≤ máxima, apertura < cierre, etc.)
 * las hace el backend; devuelve 422 con `detail` si algo no valida.
 */
export async function setExamConfig(
  examenId: string,
  patch: Partial<ExamConfig>,
): Promise<ExamConfig> {
  const res = await fetchAutenticado(`${API_BASE}/exam-content/${examenId}/config`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.mensaje ?? body?.detail ?? `Error ${res.status}`);
  }
  return res.json() as Promise<ExamConfig>;
}

// ---------------------------------------------------------------------------
// Selección de preguntas del examen (opción B): el tutor elige qué preguntas
// del pool importado forman el examen. El alumno rinde solo las seleccionadas.
// ---------------------------------------------------------------------------

/** Tipo de pregunta importada desde Moodle (sin es_correcta: admin no ve la clave). */
export type PreguntaTipo = 'multichoice' | 'truefalse';

/** Una pregunta del pool del examen, con su estado de inclusión actual. */
export interface PreguntaSeleccion {
  id: string;
  enunciado: string;
  tipo: PreguntaTipo | string;
  orden: number;
  seleccionada: boolean;
}

/** Respuesta del listado de preguntas del pool + contadores. */
export interface PreguntasExamenResponse {
  items: PreguntaSeleccion[];
  total: number;
  seleccionadas: number;
  /**
   * true si el examen ya tiene ≥ 1 intento FINALIZADO: la selección quedó
   * CONGELADA. Cambiarla alteraría notas ya calculadas (grade_calculator cuenta
   * solo las seleccionadas), por eso el PATCH devuelve 409. La UI usa este flag
   * para deshabilitar el editor ANTES de que el tutor intente guardar.
   */
  bloqueada?: boolean;
}

/**
 * Lista TODAS las preguntas del pool importado del examen, cada una con su flag
 * `seleccionada` (si forma parte del examen que rinde el alumno). Admin-only.
 * GET /api/v1/exam-content/{examenId}/preguntas
 */
export async function getPreguntasExamen(examenId: string): Promise<PreguntasExamenResponse> {
  const res = await fetchAutenticado(`${API_BASE}/exam-content/${examenId}/preguntas`, {
    method: 'GET',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.mensaje ?? body?.detail ?? `Error ${res.status}`);
  }
  return res.json() as Promise<PreguntasExamenResponse>;
}

/**
 * Arma la selección del examen por sorteo: elige aleatoriamente `cantidadPorCategoria`
 * preguntas de cada categoría indicada y las marca como seleccionadas. Admin-only.
 * POST /api/v1/exam-content/{examenId}/sortear-preguntas
 */
export async function sortearPreguntas(
  examenId: string,
  categoriaIds: string[],
  cantidadPorCategoria: number,
): Promise<{ seleccionadas: number }> {
  const res = await fetchAutenticado(`${API_BASE}/exam-content/${examenId}/sortear-preguntas`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ categoria_ids: categoriaIds, cantidad_por_categoria: cantidadPorCategoria }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.mensaje ?? body?.detail ?? `Error ${res.status}`);
  }
  const body = await res.json().catch(() => null);
  return { seleccionadas: body?.seleccionadas ?? 0 };
}

/**
 * Define la selección de preguntas del examen: `seleccionadasIds` son los ids
 * INCLUIDOS. El backend rechaza con 422 si la lista queda vacía (un examen no
 * puede quedar sin preguntas). Admin-only. Devuelve los contadores resultantes
 * (tolera cuerpo vacío en la respuesta).
 * PATCH /api/v1/exam-content/{examenId}/preguntas-seleccion
 */
export async function setPreguntasSeleccion(
  examenId: string,
  seleccionadasIds: string[],
): Promise<{ seleccionadas: number }> {
  const res = await fetchAutenticado(`${API_BASE}/exam-content/${examenId}/preguntas-seleccion`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ seleccionadas: seleccionadasIds }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.mensaje ?? body?.detail ?? `Error ${res.status}`);
  }
  const body = await res.json().catch(() => null);
  return { seleccionadas: body?.seleccionadas ?? seleccionadasIds.length };
}

// ---------------------------------------------------------------------------
// C-69: alumnos inscriptos por comisión + elegibilidad ("puede rendir").
// Endpoints admin-only bajo /api/v1/exam-content/ (mismo guard Bearer).
// Manejo de error con throwAdminError → el Error lleva `.status` HTTP para que
// la UI distinga 409 (ya inscripto) / 404 (comisión o usuario no existe).
// ---------------------------------------------------------------------------

/** Resultado de inscribir un alumno a una comisión. POST devuelve 201. */
export interface InscripcionAlumnoResponse {
  id: string;
  usuario_id: string;
  comision_id: string;
}

/** Lista los alumnos inscriptos a una comisión con su elegibilidad para rendir.
 *  Admin-only. GET /exam-content/comisiones/{comisionId}/alumnos.
 *  404 → la comisión no existe. */
export interface AlumnosComisionPaginados {
  items: AlumnoInscripto[];
  total: number;
  page: number;
  page_size: number;
}

export async function listarAlumnosDeComision(
  comisionId: string,
  params: { page?: number; page_size?: number } = {},
): Promise<AlumnosComisionPaginados> {
  // c-78 §13.2: el endpoint pasó a devolver { items, total, page, page_size }.
  // Con 40 alumnos por comisión el listado completo era ilegible.
  const qs = new URLSearchParams();
  if (params.page !== undefined) qs.set('page', String(params.page));
  if (params.page_size !== undefined) qs.set('page_size', String(params.page_size));
  const cola = qs.toString();
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/comisiones/${encodeURIComponent(comisionId)}/alumnos${
      cola ? '?' + cola : ''
    }`,
    {
      method: 'GET',
      headers: authHeaders(),
    },
  );
  if (!res.ok) return throwAdminError(res);
  return res.json() as Promise<AlumnosComisionPaginados>;
}

/**
 * URL de descarga de un export académico (c-78 §13.4/§13.5).
 *
 * Se devuelve la URL en vez de los bytes a propósito: la descarga la dispara el
 * navegador con el token en el header, vía `descargarExport` — así el archivo
 * no pasa por memoria de JS ni hay que armar un blob para algo que el navegador
 * ya sabe hacer.
 */
export type FormatoExport = 'xlsx' | 'pdf';

export function urlExportInscriptos(comisionId: string, formato: FormatoExport): string {
  return `${API_BASE}/exam-content/comisiones/${encodeURIComponent(
    comisionId,
  )}/alumnos/export.${formato}`;
}

export function urlExportNotas(examenId: string, formato: FormatoExport): string {
  return `${API_BASE}/exam-content/${encodeURIComponent(examenId)}/notas/export.${formato}`;
}

/**
 * Descarga un export autenticado y se lo entrega al navegador.
 *
 * Un `<a href>` pelado no sirve: estos endpoints exigen Bearer, y el navegador
 * no lo manda en una navegación. Se baja con fetch y se dispara la descarga
 * desde un blob temporal, que se revoca enseguida.
 */
export async function descargarExport(url: string, nombreSugerido: string): Promise<void> {
  const res = await fetchAutenticado(url, { method: 'GET', headers: authHeaders() });
  if (!res.ok) return throwAdminError(res);
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  try {
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = nombreSugerido;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

/** Inscribe un alumno (usuario rol estudiante) a una comisión. Admin-only.
 *  POST /exam-content/comisiones/{comisionId}/inscripciones → 201.
 *  409 → ya inscripto  |  404 → comisión o usuario no existe. */
export async function inscribirAlumno(
  comisionId: string,
  usuarioId: string,
): Promise<InscripcionAlumnoResponse> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/comisiones/${encodeURIComponent(comisionId)}/inscripciones`,
    {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ usuario_id: usuarioId }),
    },
  );
  if (!res.ok) return throwAdminError(res);
  return res.json() as Promise<InscripcionAlumnoResponse>;
}

/** Elimina la inscripción de un alumno a una comisión. Admin-only.
 *  DELETE /exam-content/comisiones/{comisionId}/inscripciones/{usuarioId} → 204.
 *  404 → el alumno no estaba inscripto. No hay cuerpo en la respuesta. */
export async function eliminarInscripcion(
  comisionId: string,
  usuarioId: string,
): Promise<void> {
  const res = await fetchAutenticado(
    `${API_BASE}/exam-content/comisiones/${encodeURIComponent(comisionId)}/inscripciones/${encodeURIComponent(usuarioId)}`,
    {
      method: 'DELETE',
      headers: authHeaders(),
    },
  );
  if (!res.ok) return throwAdminError(res);
}
