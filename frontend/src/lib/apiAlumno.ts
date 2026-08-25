// Métodos del portal del alumno extraídos de api.ts (refactor c-76: partir god-file).
// Catálogo navegable (materias/comisiones/exámenes), inscripción por código, notas,
// informe de devolución y revisión post-examen. Se spreadean en `api` (./api).
import { API_BASE, realFetch } from './apiCore';
import { authProvider } from './authProvider';
import type { Materia, Comision, ComisionConMateria, Inscripcion, ExamenContenidoResumen, NotaExamen, MisNotasResponse, InformeDevolucion, RevisionExamen } from './types';

export const alumnoApi = {
  // -------------------------------------------------------------------------
  // Portal del alumno — API (C-21)
  // -------------------------------------------------------------------------

  /** 2.7 Materias disponibles (C-69): GET /exam-content/materias.
   *
   * `strict` (c-78 D16) PROPAGA el fallo en vez de devolver []. Lo usan las
   * pantallas que tienen que distinguir "no hay materias" de "no pudo cargar";
   * los selectores y filtros siguen con el default silencioso. */
  async materiasDisponibles(strict = false): Promise<Materia[]> {
    const { listarMateriasFn } = await import('./examContentBrowse');
    return listarMateriasFn(API_BASE, authProvider.getToken(), strict);
  },

  /** Periodos académicos válidos para una comisión.
   * GET /exam-content/periodos → [{value, label}] (sin auth). */
  async listarPeriodos(): Promise<{ value: string; label: string }[]> {
    return realFetch<{ value: string; label: string }[]>('/exam-content/periodos', { method: 'GET' });
  },

  /** 2.8 Comisiones de una materia (C-69):
   * GET /exam-content/materias/{id}/comisiones. */
  async comisionesDeMateria(materiaId: string, strict = false): Promise<Comision[]> {
    const { listarComisionesFn } = await import('./examContentBrowse');
    return listarComisionesFn(API_BASE, authProvider.getToken(), materiaId, strict);
  },

  /** GET /exam-content/comisiones → TODAS las comisiones, con su materia embebida.
   * Selector combinado único ("CÓDIGO - Materia"), sin elegir materia primero. */
  async comisionesTodas(): Promise<ComisionConMateria[]> {
    const { listarTodasComisionesFn } = await import('./examContentBrowse');
    return listarTodasComisionesFn(API_BASE, authProvider.getToken());
  },

  /** 2.9 Exámenes de una comisión (contenido importado de Moodle) (C-69):
   * GET /exam-content/comisiones/{id}/examenes → ExamenContenidoResumen[]. */
  async examenesDeComision(comisionId: string): Promise<ExamenContenidoResumen[]> {
    const { listarExamenesDeComisionFn } = await import('./examContentBrowse');
    return listarExamenesDeComisionFn(API_BASE, authProvider.getToken(), comisionId);
  },

  /** C-70: el alumno se auto-matricula a una comisión con un código (enrolment key).
   *  Lanza Error con `.status` (404/422) si el código es inválido. */
  async inscribirmePorCodigo(codigo: string) {
    const { inscribirmePorCodigoFn } = await import('./examContentBrowse');
    return inscribirmePorCodigoFn(API_BASE, authProvider.getToken(), codigo);
  },

  /** 2.11 Retorna las inscripciones del alumno.
   * NO existe el modelo de inscripción: el alumno rinde directamente los exámenes de
   * contenido importados (Moodle XML). Devolvemos [] (sin sección de inscripciones). */
  async misInscripciones(): Promise<Inscripcion[]> {
    return [];
  },

  /**
   * Lista las notas académicas de los exámenes rendidos por el alumno (C-69).
   * GET /api/v1/exam-content/mis-notas → { items: NotaExamen[], total }. La nota se
   * calcula y el estado de cola de revisión lo decide el backend (fuente de verdad);
   * el cliente solo la muestra. Degradación silenciosa: un error de red retorna [].
   */
  async misNotas(): Promise<NotaExamen[]> {
    try {
      const resp = await realFetch<MisNotasResponse>('/exam-content/mis-notas', { method: 'GET' });
      return resp.items ?? [];
    } catch {
      return [];
    }
  },

  /**
   * C-71 slice 2 (D12): informe de devolución del alumno para SU sesión anulada
   * por fraude. GET /exam-content/mis-notas/{sessionId}/informe. Solo existe si la
   * nota del titular fue anulada por fraude (minimización, Ley 25.326); en cualquier
   * otro caso el backend responde 404 → devolvemos null. El acceso queda auditado
   * server-side como ejercicio del derecho de acceso del titular (RN-DSR-01).
   */
  async informeDevolucion(sessionId: string): Promise<InformeDevolucion | null> {
    try {
      return await realFetch<InformeDevolucion>(
        `/exam-content/mis-notas/${encodeURIComponent(sessionId)}/informe`,
        { method: 'GET' },
      );
    } catch {
      return null;
    }
  },

  /**
   * C-69: revisión post-examen del alumno para un examen. Devuelve la corrección
   * (es_correcta + la opción elegida) del intento FINALIZADO del alumno.
   * Real: GET /exam-content/{examen_id}/revision → 200 revisión; 404 si el alumno
   * no tiene un intento finalizado para ese examen.
   * Devuelve null en 404/error (la UI muestra "revisión no disponible").
   */
  async revisionExamen(examenId: string): Promise<RevisionExamen | null> {
    try {
      return await realFetch<RevisionExamen>(
        `/exam-content/${examenId}/revision`,
        { method: 'GET' },
      );
    } catch {
      return null;
    }
  },
};
