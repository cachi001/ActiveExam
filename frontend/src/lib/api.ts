// Capa de API del MVP. Por defecto funciona en MODO DEMO (datos en memoria, sin
// backend) para poder probar el flujo completo standalone. Si se define
// VITE_API_BASE + VITE_USE_REAL_BACKEND=1, las llamadas marcadas como reales
// (consentimiento, biometría) pasan por fetch al FastAPI real.
//
// Los esquemas y enums coinciden con app/presentation/api/v1/* del backend.

import type {
  Principal, Rol, ConsentTextResponse, ConsentResponse, Examen,
  EventoSesion, DesafioActivo, Severidad, TipoEvento,
  Materia, Comision, Inscripcion, EstadoInscripcion,
  EstadoEnrollment, AcuseConsentimiento, BloqueConsentimiento, ReferenciasBiometrica, EscaneDNI, VigenciaReferencia,
  SesionProctoringResumen, SesionProctoringDetalle, EventoProctoringDetalle,
  BiometriaDetalle, VeredictoReinferencia,
  // C-15: chat bidireccional + pausa autorizada + acciones del proctor
  MensajeChat, AutorChat, Pausa, AccionPausa, PausaPendiente, ObservacionProctor, CierreForzado,
  // C-61: gestión de usuarios
  UsuarioAdmin, ListarUsuariosResponse,
  // #10: configuracion de scoring por tipo de evento
  EventoScoreConfig,
  // C-69: catálogo de exámenes de contenido importados
  ExamenContenidoResumen,
  // C-69: notas académicas del alumno + estado de cola de revisión
  NotaExamen, MisNotasResponse, RevisionExamen,
  // C-71 slice 2: informe de devolución del alumno (solo nota anulada por fraude)
  InformeDevolucion,
  // C-71 slice 2: decisión del revisor (dos fases) — cableado de la cola (C-72 backlog UX)
  DecisionRevision, DecisionResolucion,
} from './types';
import { INSTITUTION } from '../config/institution';
import { authProvider } from './authProvider';

export const API_BASE = (import.meta.env.VITE_API_BASE as string) || '/api/v1';

const delay = (ms = 350) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------------------
// Catálogo académico local (usado por joinExamInfo en las pantallas de proctoring)
// ---------------------------------------------------------------------------

export const PRINCIPALES: Record<Rol, Principal> = {
  estudiante: {
    id_institucional: 'FRM-23-4912', nombre: 'Emiliano Cáceres',
    email: 'ecaceres@frm.utn.edu.ar', roles: ['estudiante'],
    mfa_satisfecho: true, jurisdiccion: 'AR-MZA',
  },
  proctor: {
    id_institucional: `${INSTITUTION.idPrefix}-DOC-1182`, nombre: 'Dra. Carolina Ferreyra',
    email: `cferreyra@${INSTITUTION.dominioEmail}`, roles: ['proctor'], mfa_satisfecho: true, jurisdiccion: 'AR',
  },
  admin_sistema: {
    id_institucional: `${INSTITUTION.idPrefix}-ADM-0021`, nombre: 'Lucía Mendoza',
    email: `lmendoza@${INSTITUTION.dominioEmail}`, roles: ['admin_sistema'], mfa_satisfecho: true, jurisdiccion: 'AR',
  },
};

const DETECTORES_DEFAULT: TipoEvento[] = [
  'rostro_ausente', 'multiples_rostros', 'mirada_desviada_sostenida',
  'perdida_de_foco', 'cambio_pestana', 'monitor_adicional',
  'salida_pantalla_completa', 'copiar_pegar',
];

type ExamenConComision = Examen & { comision_id?: string };

// Un único examen "rendible" para probar el flujo completo sin clutter.
// `estado: 'en_curso'` → es el que Login.tsx selecciona como `examenActivo`.
const EXAMEN_RENDIBLE_ID = `EX-${INSTITUTION.idPrefix}-AMAT-I`;

// Exportados para que el catálogo académico pueda joinearse desde la UI
// (joinExamInfo en screens/proctoring/helpers.ts). Lectura pura, sin mutación externa.
export let EXAMENES: ExamenConComision[] = [
  {
    id: EXAMEN_RENDIBLE_ID, nombre: 'Examen Final — Análisis Matemático I', catedra: 'Cátedra B',
    estado: 'en_curso', inicio: '2026-05-30T14:00:00', duracion_min: 60,
    umbral_score: 70, detectores: DETECTORES_DEFAULT, retencion_dias: 30,
    inscriptos: 48, rindiendo: 4, comision_id: 'COM-AMAT-1A',
  },
];

// ---------------------------------------------------------------------------
// Portal del alumno — catálogo académico local (C-21)
// ---------------------------------------------------------------------------

// 2.2 Materias UTN FRM
export const MATERIAS: Materia[] = [
  { id: 'MAT-AMAT', nombre: 'Análisis Matemático I', codigo: 'CB101', descripcion: 'Funciones, límites, derivadas e integrales. Fundamentos del cálculo diferencial e integral.' },
  { id: 'MAT-FIS1', nombre: 'Física I', codigo: 'CB102', descripcion: 'Mecánica clásica, cinemática, dinámica y termodinámica básica.' },
  { id: 'MAT-PROG', nombre: 'Programación I', codigo: 'SIS101', descripcion: 'Introducción a la programación estructurada. Algoritmos, estructuras de datos básicas.' },
];

// 2.3 Comisiones (≥2 por materia)
export const COMISIONES: Comision[] = [
  { id: 'COM-AMAT-1A', materia_id: 'MAT-AMAT', nombre: 'Comisión 1A', docente: 'Dr. Roberto Fernández', horario: 'Lunes y Miércoles 08:00–10:00' },
  { id: 'COM-AMAT-1B', materia_id: 'MAT-AMAT', nombre: 'Comisión 1B', docente: 'Dra. Laura Giménez', horario: 'Martes y Jueves 10:00–12:00' },
  { id: 'COM-FIS1-2A', materia_id: 'MAT-FIS1', nombre: 'Comisión 2A', docente: 'Ing. Carlos Pérez', horario: 'Lunes y Viernes 14:00–16:00' },
  { id: 'COM-FIS1-2B', materia_id: 'MAT-FIS1', nombre: 'Comisión 2B', docente: 'Dr. Alejandro Torres', horario: 'Miércoles y Viernes 08:00–10:00' },
  { id: 'COM-PROG-1A', materia_id: 'MAT-PROG', nombre: 'Comisión 1A', docente: 'Ing. Valeria Romero', horario: 'Martes y Jueves 16:00–18:00' },
  { id: 'COM-PROG-1B', materia_id: 'MAT-PROG', nombre: 'Comisión 1B', docente: 'Lic. Sebastián Díaz', horario: 'Lunes y Miércoles 18:00–20:00' },
];

// ---------------------------------------------------------------------------
// Enrollment biométrico del perfil — C-22
// ---------------------------------------------------------------------------

/**
 * Vigencia de la referencia en meses (configurable, NO hardcode).
 * En producción vendría de una variable de entorno / config del servidor.
 */
export const BIOMETRIC_VALIDITY_MONTHS: number =
  Number(import.meta.env.VITE_BIOMETRIC_VALIDITY_MONTHS) || 24;

/** Feature flag para el escaneo de DNI (opcional). Default ACTIVO; se desactiva con VITE_ENABLE_DNI_SCAN=0. */
export const ENABLE_DNI_SCAN: boolean =
  import.meta.env.VITE_ENABLE_DNI_SCAN !== '0';

/** Versión del motor de visión (para metadatos de la referencia). */
const VISION_ENGINE_VERSION = 'mediapipe-face-mesh-v1';

/** Calcula la fecha de expiración dado la fecha de captura y los meses de vigencia. */
function calcularExpiracion(fechaCaptura: string, meses: number): string {
  const d = new Date(fechaCaptura);
  d.setMonth(d.getMonth() + meses);
  return d.toISOString();
}

/** Calcula el estado de vigencia de una referencia biométrica. */
function calcularVigencia(fechaExpiracion: string, renovacionAnticipada: boolean): VigenciaReferencia {
  if (renovacionAnticipada) return 'renovacion_requerida';
  const ahora = new Date();
  const expira = new Date(fechaExpiracion);
  const diasRestantes = (expira.getTime() - ahora.getTime()) / (1000 * 60 * 60 * 24);
  if (diasRestantes <= 0) return 'caducada';
  if (diasRestantes <= 90) return 'por_vencer'; // aviso 3 meses antes
  return 'vigente';
}

/**
 * Estado in-memory del enrollment del alumno (C-22).
 * Reemplaza el antiguo `perfilAlumno = { consentimiento_ok, biometria_ok }`.
 */
// Demo: persistir el enrollment y la foto en localStorage para que NO se pierdan
// al recargar la página (el mock vive en memoria; sin esto, consentimiento/foto se borran).
const LS_ENROLLMENT = 'ae_demo_enrollment';
const LS_FOTO = 'ae_demo_foto_perfil';

function loadEnrollmentFromLS(): EstadoEnrollment {
  try {
    const raw = localStorage.getItem(LS_ENROLLMENT);
    if (raw) return JSON.parse(raw) as EstadoEnrollment;
  } catch { /* ignore */ }
  return { consentimiento: null, biometria: null, dni: null, perfil_completo: false };
}

let enrollmentAlumno: EstadoEnrollment = loadEnrollmentFromLS();

/** Persiste el enrollment del alumno (demo: sobrevive recargas). */
function persistEnrollment(): void {
  try { localStorage.setItem(LS_ENROLLMENT, JSON.stringify(enrollmentAlumno)); } catch { /* ignore */ }
}

/** Asigna + recalcula perfil_completo + persiste, en un solo paso. */
function commitEnrollment(e: EstadoEnrollment): EstadoEnrollment {
  const next = recalcularPerfilCompleto(e);
  enrollmentAlumno = next;
  persistEnrollment();
  return enrollmentAlumno;
}

// Restaurar la foto de perfil persistida (demo) al avatar del estudiante.
try {
  const fotoLS = localStorage.getItem(LS_FOTO);
  if (fotoLS) PRINCIPALES.estudiante = { ...PRINCIPALES.estudiante, foto_perfil: fotoLS };
} catch { /* ignore */ }

/**
 * Estado in-memory de las solicitudes de vía alternativa (C-63).
 * Clave: examId (o "perfil"). Valor: estado actual.
 */
const _estadosViaAlternativa = new Map<string, string>();

/** Recalcula `perfil_completo` según las reglas del gate. */
function recalcularPerfilCompleto(e: EstadoEnrollment): EstadoEnrollment {
  const consentimientoValido =
    e.consentimiento !== null &&
    (e.consentimiento.via_alternativa || e.consentimiento.version === consentVersionVigente());

  const biometriaVigente =
    (e.biometria !== null &&
      e.biometria.captura_completada &&
      e.biometria.vigencia !== 'caducada');

  return { ...e, perfil_completo: consentimientoValido && biometriaVigente };
}

// ---------------------------------------------------------------------------
// Acuses por-examen — C-26
// ---------------------------------------------------------------------------

export const DESAFIOS: DesafioActivo[] = [
  // Legacy (C-09)
  { id: 'girar_izquierda', label: 'Girar a la izquierda' },
  { id: 'girar_derecha', label: 'Girar a la derecha' },
  { id: 'parpadear', label: 'Parpadear' },
  { id: 'acercarse', label: 'Acercarse a la cámara' },
  { id: 'sonreir', label: 'Sonreír' },
  // C-54: catálogo secuencial
  { id: 'girar_cabeza', label: 'Girar la cabeza' },
  { id: 'sonreír', label: 'Sonreír' },
];

const DESC_EVENTO: Record<TipoEvento, string> = {
  rostro_ausente: 'No se detectó rostro en el encuadre por más de 3 segundos.',
  multiples_rostros: 'Se detectaron múltiples rostros simultáneos en cámara.',
  mirada_desviada_sostenida: 'Patrón de mirada sostenido hacia un punto fijo fuera de pantalla.',
  perdida_de_foco: 'El estudiante minimizó la ventana o la ventana perdió el foco del sistema operativo.',
  cambio_pestana: 'El estudiante cambió o abrió otra pestaña del navegador durante el examen.',
  monitor_adicional: 'Se detectó un segundo monitor conectado al equipo.',
  salida_pantalla_completa: 'El estudiante salió del modo de pantalla completa durante el examen.',
  copiar_pegar: 'Se detectó una acción de copiar o pegar durante el examen (sin capturar contenido).',
  corte_conectividad_prolongado: 'Corte de conectividad prolongado (> 5 min) con el canal de eventos.',
  recarga_pagina: 'El estudiante recargó la página y volvió enseguida (reapertura benigna).',
  reanudacion_tardia: 'El estudiante reanudó la rendición tras una ausencia prolongada.',
};

export function descripcionEvento(t: TipoEvento): string { return DESC_EVENTO[t]; }

const CONSENT_TEXT: ConsentTextResponse = {
  // Alineada con la versión del backend real ('v1') para que demo y real coincidan
  // y la versión del consentimiento se muestre igual en todo el sistema.
  version: 'v1',
  hash_texto: 'sha256:9f2b…a31',
  bloques: [
    { icono: 'help', titulo: '¿Qué datos recolectamos?', cuerpo: 'Video de tu cámara y captura de pantalla durante el examen, y un descriptor facial para verificar tu identidad. El descriptor biométrico se trata como dato sensible.' },
    { icono: 'memory', titulo: '¿Cómo se procesan?', cuerpo: 'El análisis de visión corre localmente en tu navegador (Web Worker). Solo se envían señales discretas firmadas y, ante incidencias graves, clips cortos de evidencia. El backend re-infiere y firma toda la evidencia.' },
    { icono: 'dns', titulo: '¿Dónde se almacenan?', cuerpo: 'En infraestructura self-hosted de la universidad, cifrada en reposo, con cadena de custodia criptográfica. Soberanía de datos completa.' },
    { icono: 'schedule', titulo: '¿Cuánto tiempo?', cuerpo: 'La evidencia se conserva 30 días y luego se elimina automáticamente. El embedding biométrico se elimina al egreso, salvo apelación o hold disciplinario.' },
    { icono: 'gavel', titulo: 'Tus derechos', cuerpo: 'El sistema nunca sanciona automáticamente: solo prioriza para revisión humana. Podés acceder, rectificar y solicitar la eliminación de tus datos.' },
  ],
};

// Versión vigente del texto de consentimiento. En modo demo es la del mock
// (`CONSENT_TEXT.version`); con backend real, `getConsentText` la actualiza con la
// versión que devuelve el catálogo del backend (p. ej. "v1"). El gate de perfil
// compara la versión del acuse contra ESTA, no contra la constante mock — si no,
// real backend ("v1") nunca coincide con el mock ("2026.1") y el perfil queda
// eternamente "incompleto: renovación del consentimiento".
let _consentVersionVigente: string = CONSENT_TEXT.version;
function consentVersionVigente(): string {
  return _consentVersionVigente;
}

// C-67: la versión vigente del consentimiento sólo se sincronizaba con el backend
// cuando se abría la pantalla de consentimiento (getConsentText). Tras un reload que
// aterriza directo en el dashboard, `_consentVersionVigente` volvía al default mock
// ('2026.1') y el gate de perfil lo comparaba contra el acuse guardado ('v1' real) →
// falso "consentimiento desactualizado" → tarjeta amarilla "completá tu perfil" aunque
// el perfil estuviera completo. Sincronizamos la versión del backend ANTES de evaluar
// el gate (una vez por sesión; un reload vuelve a sincronizar y detecta cambios reales).
async function ensureConsentVersionSynced(): Promise<void> {
  // SIEMPRE re-sincroniza la versión vigente desde el backend (no cachear por sesión):
  // si el admin publica una versión nueva mientras el alumno está logueado, el gate
  // del inicio debe detectarlo SIN que tenga que ir al perfil y volver. Es un GET chico.
  try {
    const texto = normalizarConsentText(await realFetch<unknown>('/consent/text', { method: 'GET' }));
    if (texto.version) _consentVersionVigente = texto.version;
  } catch {
    // Fallo de red: no bloquear el gate. Se reintenta en la próxima llamada.
  }
}

/**
 * Refresca el enrollment del alumno con el estado FRESCO del servidor (modo real) y
 * recalcula `perfil_completo`. Es la fuente única para `getEnrollment` y `puedeRendir`:
 * el gate NUNCA debe decidir con el cache local (localStorage `ae_demo_enrollment`),
 * que puede mentir tras un reset de DB (tmpfs) o un cambio de usuario en el mismo browser.
 *
 * En modo demo no hay servidor: sólo re-sincroniza la versión del consentimiento y
 * recalcula el perfil desde el estado en memoria (comportamiento previo intacto).
 */
async function syncEnrollmentState(): Promise<EstadoEnrollment> {
  // C-67: la versión vigente del consentimiento debe venir del backend antes de
  // recalcular el perfil, para no invalidar un acuse real ('v1' vs mock).
  await ensureConsentVersionSynced();

  {
    const token = authProvider.getToken?.() ?? '';
    const headers = { Authorization: `Bearer ${token}` };
    const [consentResp, biometriaResp] = await Promise.all([
      fetch(`${API_BASE}/consent/profile`, { headers })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null),
      fetch(`${API_BASE}/proctoring/biometria/referencia/estado`, { headers })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null),
    ]);

    const consentimiento: AcuseConsentimiento | null =
      consentResp && consentResp.estado === 'otorgado'
        ? {
            version: consentResp.version_texto ?? consentVersionVigente(),
            timestamp: consentResp.timestamp ?? new Date().toISOString(),
            hash: consentResp.hash_texto ?? '',
            via_alternativa: false,
          }
        : null;

    const tieneRefVigente = Boolean(biometriaResp?.tiene_referencia_vigente);
    // El backend solo expone el booleano (RN-BIO/Ley 25.326). Si no había cache
    // local, sintetizamos un stub mínimo que satisface el tipo sin filtrar dato.
    const biometriaStub: ReferenciasBiometrica = enrollmentAlumno.biometria ?? {
      captura_completada: true,
      imagen: null,
      embedding: null,
      fecha_captura: new Date().toISOString(),
      fecha_expiracion: new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString(),
      vigencia_meses: 12,
      version_motor: 'server',
      vigencia: 'vigente',
      renovacion_anticipada_requerida: false,
    };
    const biometria: ReferenciasBiometrica | null = tieneRefVigente
      ? { ...biometriaStub, captura_completada: true, vigencia: 'vigente' }
      : null;

    const next: EstadoEnrollment = {
      consentimiento,
      biometria,
      dni: enrollmentAlumno.dni,
      perfil_completo: false, // recalcularPerfilCompleto lo decide en commitEnrollment
    };
    commitEnrollment(next);
    return { ...enrollmentAlumno };
  }
}

/**
 * Invalida el enrollment cacheado del alumno (cache en memoria + localStorage +
 * acuses por-examen + estados de vía alternativa). Se llama al iniciar/cerrar sesión
 * para que un usuario NO herede el `perfil_completo` (ni los acuses) del usuario
 * anterior en el mismo browser. El siguiente `getEnrollment`/`puedeRendir` lo
 * reconstruye desde el servidor (modo real).
 */
export function resetEnrollmentCache(): void {
  enrollmentAlumno = { consentimiento: null, biometria: null, dni: null, perfil_completo: false };
  try { localStorage.removeItem(LS_ENROLLMENT); } catch { /* ignore */ }
  _estadosViaAlternativa.clear();
}

// ---------------------------------------------------------------------------
// API pública. Cada método pega al backend real.
// ---------------------------------------------------------------------------

// El token sale del provider activo (authProvider.getToken()). El 3er parámetro
// legacy se ignora (los callers históricos pasaban 'demo'); se mantiene por
// compatibilidad de firma.
async function realFetch<T>(path: string, init: RequestInit, _legacyToken?: string): Promise<T> {
  const token = authProvider.getToken();
  let res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
  });

  // C-67: el access token JWT vive sólo 15 min. En flujos largos (la captura
  // biométrica con gestos lentos) expira a mitad de camino y el backend responde
  // 401. Intentamos UN refresh con el refresh_token y reintentamos el request una
  // sola vez. Sin esto el alumno quedaba clavado en 401 aunque tuviera un
  // refresh_token válido en sessionStorage (getToken devolvía undefined sin refrescar).
  if (res.status === 401 && authProvider.refresh) {
    const fresh = await authProvider.refresh();
    if (fresh) {
      res = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${fresh}`,
          ...(init.headers || {}),
        },
      });
    }
  }

  if (!res.ok) {
    // Adjuntamos el status code para que los callers puedan ramificar (p.ej. el
    // 409 de "pausa ya resuelta" en C-15) sin parsear el mensaje a mano.
    const err = new Error(`HTTP ${res.status}`) as Error & {
      status?: number;
      code?: string;
      mensaje?: string;
    };
    err.status = res.status;
    // Adjuntar el código de error del backend ({detail:{error, mensaje}}) para que
    // los callers distingan casos con el mismo status (C-72: tiempo_agotado vs
    // sesion_finalizada, ambos 409). Body no-JSON → solo status.
    try {
      const body = await res.clone().json();
      const detail = body?.detail;
      if (detail && typeof detail === 'object') {
        if (typeof detail.error === 'string') err.code = detail.error;
        if (typeof detail.mensaje === 'string') err.mensaje = detail.mensaje;
      }
    } catch {
      /* body vacío o no-JSON: se conserva solo el status */
    }
    throw err;
  }
  return res.json() as Promise<T>;
}

// El backend (app/.../consent/schemas.py) serializa `bloques` como dict[str, str]
// con las cinco claves canónicas (que/como/donde/cuanto/derechos), mientras que la
// UI consume `BloqueConsentimiento[]` (título + cuerpo + icono). Acá traducimos esa
// forma del backend a la del frontend, en el límite de la API (el dato del backend
// es no confiable: nunca debe llegar crudo a un componente que hace `.map`).
const BLOQUE_META: Record<string, { titulo: string; icono: string }> = {
  que_se_recolecta: { titulo: '¿Qué datos recolectamos?', icono: 'database' },
  como_se_recolecta: { titulo: '¿Cómo se procesan?', icono: 'memory' },
  donde_se_almacena: { titulo: '¿Dónde se almacenan?', icono: 'dns' },
  cuanto_tiempo: { titulo: '¿Cuánto tiempo?', icono: 'schedule' },
  derechos_titular: { titulo: 'Tus derechos', icono: 'gavel' },
};

/**
 * Cuando el backend devuelve bloques desde la tabla `consent_texto_version`
 * solo trae {titulo, cuerpo} (sin icono). Inferimos el icono por heurística
 * sobre el titulo — fallback `description` para versiones custom.
 */
function inferirIconoBloque(titulo: string): string {
  const t = titulo.toLowerCase();
  if (t.includes('qué datos') || t.includes('que datos') || t.includes('recolect')) return 'database';
  if (t.includes('cómo') || t.includes('como')) return 'memory';
  if (t.includes('dónde') || t.includes('donde') || t.includes('guard') || t.includes('almacen')) return 'dns';
  if (t.includes('cuánto') || t.includes('cuanto') || t.includes('tiempo') || t.includes('conserv') || t.includes('retenc')) return 'schedule';
  if (t.includes('derecho')) return 'gavel';
  return 'description';
}

/**
 * Normaliza la respuesta de `/consent/text` a la forma del frontend.
 * Acepta tanto el array ya tipado como el `dict[str, str]` del backend real
 * (orden canónico del catálogo), garantizando que `bloques` SIEMPRE sea un array.
 */
function normalizarConsentText(raw: unknown): ConsentTextResponse {
  const r = (raw ?? {}) as { version?: string; hash_texto?: string; bloques?: unknown };
  let bloques: BloqueConsentimiento[];
  if (Array.isArray(r.bloques)) {
    bloques = (r.bloques as Array<{ titulo: string; cuerpo: string; icono?: string }>).map((b) => ({
      titulo: b.titulo,
      cuerpo: b.cuerpo,
      icono: b.icono || inferirIconoBloque(b.titulo),
    }));
  } else if (r.bloques && typeof r.bloques === 'object') {
    const dict = r.bloques as Record<string, string>;
    // Orden canónico de BLOQUE_META primero; cualquier clave extra se anexa.
    const claves = [
      ...Object.keys(BLOQUE_META).filter((k) => k in dict),
      ...Object.keys(dict).filter((k) => !(k in BLOQUE_META)),
    ];
    bloques = claves.map((clave) => ({
      titulo: BLOQUE_META[clave]?.titulo ?? clave,
      icono: BLOQUE_META[clave]?.icono ?? 'info',
      cuerpo: dict[clave],
    }));
  } else {
    bloques = [];
  }
  return { version: r.version ?? '', hash_texto: r.hash_texto ?? '', bloques };
}

export const api = {
  async getConsentText(token = 'demo'): Promise<ConsentTextResponse> {
    // El backend devuelve `bloques` como dict[str, str]; normalizamos a array.
    const texto = normalizarConsentText(await realFetch<unknown>('/consent/text', { method: 'GET' }, token));
    // Sincronizar la versión vigente para el gate de perfil (evita falso "renovación").
    _consentVersionVigente = texto.version || _consentVersionVigente;
    return texto;
  },

  async recordConsent(examId: string, token = 'demo'): Promise<ConsentResponse> {
    return await realFetch<ConsentResponse>('/consent', {
      method: 'POST',
      body: JSON.stringify({ exam_id: examId, version_texto: CONSENT_TEXT.version, affirmative_action: true }),
    }, token);
  },

  /**
   * Consulta el estado de la referencia biométrica del usuario autenticado (C-59).
   *
   * Real (USE_REAL_BACKEND=1): GET /proctoring/biometria/referencia/estado
   *   El backend identifica al usuario por JWT y devuelve si tiene referencia vigente.
   *   La respuesta SOLO contiene el booleano; NUNCA el embedding ni el referencia_id
   *   (Ley 25.326, regla dura #7).
   *
   * Demo (USE_REAL_BACKEND=0): deriva de enrollmentAlumno.biometria?.captura_completada.
   *
   * Usar este endpoint para el gate de enrollment en el frontend ANTES de intentar
   * la verificación (evita capturar el embedding vivo solo para descubrir que no hay ref).
   */
  async estadoReferenciaBiometrica(): Promise<{ tiene_referencia_vigente: boolean }> {
    try {
      return await realFetch<{ tiene_referencia_vigente: boolean }>(
        '/proctoring/biometria/referencia/estado',
        { method: 'GET' },
      );
    } catch {
      // Si el endpoint falla (ej. red), asumir sin referencia para no bloquear.
      return { tiene_referencia_vigente: false };
    }
  },

  /**
   * Verificación biométrica 1:1 server-side (C-59, rama REAL).
   *
   * Real (USE_REAL_BACKEND=1): POST /proctoring/biometria/verificar-referencia
   *   body: { embedding_vivo, umbral? }
   *   El backend identifica al usuario por JWT, busca la referencia vigente en DB,
   *   la descifra server-side y compara. El embedding de referencia NUNCA viaja al
   *   cliente (Ley 25.326, regla dura #7).
   *   resp: { distancia, es_match, umbral }
   *   - 404: sin referencia vigente -> señal de no_enrolado (distinto de error de red).
   *   - 422: embedding_vivo de dimensión inválida.
   *   - 500: error interno de descifrado.
   *
   * DATO SENSIBLE (Ley 25.326): el embedding_vivo NO se loguea.
   */
  async verificarBiometriaReferencia(
    embeddingVivo: number[],
    umbral?: number,
  ): Promise<{ distancia: number; es_match: boolean; umbral: number }> {
    // No hace try/catch: propaga el error para que el caller distinga:
    //   - Error('HTTP 404') -> sin referencia vigente -> fase no_enrolado
    //   - Error('HTTP 422') -> embedding invalido
    //   - Error('HTTP 500') -> error interno de descifrado
    //   - Otros -> error de red
    const token = authProvider.getToken();
    const res = await fetch(`${API_BASE}/proctoring/biometria/verificar-referencia`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        embedding_vivo: embeddingVivo,
        umbral: umbral ?? null,
      }),
    });
    if (!res.ok) {
      // Lanza un error con el status HTTP para que Biometria.tsx pueda distinguir 404.
      const err = new Error(`HTTP ${res.status}`) as Error & { status: number };
      err.status = res.status;
      throw err;
    }
    return res.json() as Promise<{ distancia: number; es_match: boolean; umbral: number }>;
  },

  /**
   * Verificación biométrica 1:1 — dos ramas (real vs demo).
   *
   * RAMA REAL (USE_REAL_BACKEND=1):
   *   Llama a verificarBiometriaReferencia (POST /proctoring/biometria/verificar-referencia).
   *   Solo se envía el embedding_vivo; el backend identifica al usuario por JWT.
   *   embeddingReferencia se IGNORA en modo real (es null por diseño en C-56).
   *
   * RAMA DEMO (USE_REAL_BACKEND=0):
   *   Calcula la distancia coseno LOCALMENTE entre los dos descriptores 128-d.
   *   embeddingReferencia debe estar presente en el cliente (capturado en enrollment demo).
   *
   * DATO SENSIBLE (Ley 25.326): los embeddings NO se loguean.
   *
   * @deprecated Para modo real preferir verificarBiometriaReferencia directamente.
   *   Este método conserva retrocompat con el flujo demo existente.
   */
  async verificarBiometria(
    embeddingVivo: number[],
    _embeddingReferencia: number[],
    umbral?: number,
  ): Promise<{ distancia: number; es_match: boolean; umbral: number } | null> {
    // Rama real (C-59): solo envía el embedding vivo; el backend hace el resto.
    // embeddingReferencia se ignora intencionalmente (es null en modo real, C-56).
    try {
      return await this.verificarBiometriaReferencia(embeddingVivo, umbral);
    } catch {
      return null;
    }
  },

  /** No hay catálogo de exámenes "rendibles" server-side; los callers toleran undefined. */
  async getExam(_id: string): Promise<Examen | undefined> { return undefined; },

  // -------------------------------------------------------------------------
  // Portal del alumno — API (C-21)
  // -------------------------------------------------------------------------

  /** 2.7 Materias disponibles (C-69): GET /exam-content/materias. */
  async materiasDisponibles(): Promise<Materia[]> {
    const { listarMateriasFn } = await import('./examContentBrowse');
    return listarMateriasFn(API_BASE, authProvider.getToken());
  },

  /** Periodos académicos válidos para una comisión.
   * GET /exam-content/periodos → [{value, label}] (sin auth). */
  async listarPeriodos(): Promise<{ value: string; label: string }[]> {
    return realFetch<{ value: string; label: string }[]>('/exam-content/periodos', { method: 'GET' });
  },

  /** 2.8 Comisiones de una materia (C-69):
   * GET /exam-content/materias/{id}/comisiones. */
  async comisionesDeMateria(materiaId: string): Promise<Comision[]> {
    const { listarComisionesFn } = await import('./examContentBrowse');
    return listarComisionesFn(API_BASE, authProvider.getToken(), materiaId);
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

  // -------------------------------------------------------------------------
  // Enrollment biométrico del perfil — C-22
  // -------------------------------------------------------------------------

  /**
   * Gate de rendición (C-22): el alumno puede rendir si tiene el PERFIL COMPLETO
   * (consentimiento de perfil vigente o vía alternativa + biometría vigente). El
   * consentimiento de perfil es el único gate de consentimiento — el acuse
   * por-examen se eliminó por redundante. El gate NUNCA sanciona: deriva/flaggea (L2.5).
   */
  async puedeRendir(examenId?: string): Promise<{ puede: boolean; razon?: string; codigo?: string }> {
    await delay(200);
    // El gate debe decidir con estado FRESCO del servidor, NO con el cache local
    // (localStorage `ae_demo_enrollment`), que puede mentir tras un reset de DB o un
    // cambio de usuario en el mismo browser → flash de "disponible" stale. syncEnrollmentState
    // refetcha del backend (modo real), re-sincroniza la versión del consentimiento (C-67)
    // y recalcula `perfil_completo` antes de evaluar el gate.
    const e = await syncEnrollmentState();
    enrollmentAlumno = e;

    // C-63: verificar vía alternativa pendiente / habilitada antes del gate de perfil
    if (examenId) {
      const estadoAlt = _estadosViaAlternativa.get(examenId);
      if (estadoAlt === 'pendiente_proctor') {
        return {
          puede: false,
          codigo: 'via_alternativa_pendiente',
          razon: 'Tu verificación alternativa está pendiente de aprobación de un proctor.',
        };
      }
      if (estadoAlt === 'via_alternativa_habilitada' || estadoAlt === 'habilitado_por_proctor') {
        // Proctor habilitó — puede rendir sin biometría.
        return { puede: true };
      }
    }
    // También verificar estado del perfil para vía alternativa habilitada (enrollment)
    const estadoAltPerfil = _estadosViaAlternativa.get('perfil');
    if (estadoAltPerfil === 'via_alternativa_habilitada' || estadoAltPerfil === 'habilitado_por_proctor') {
      // El proctor habilitó el perfil — puede rendir sin biometría (C-63 D-04)
      return { puede: true };
    }

    // Capa 1: perfil completo (C-22)
    if (!e.perfil_completo) {
      const faltantes: string[] = [];
      let codigo = 'perfil_incompleto';

      if (!e.consentimiento) {
        faltantes.push('consentimiento informado');
      } else if (!e.consentimiento.via_alternativa && e.consentimiento.version !== consentVersionVigente()) {
        faltantes.push('renovación del consentimiento (nueva versión disponible)');
        codigo = 'consentimiento_version_desactualizada';
      }

      if (!e.consentimiento?.via_alternativa) {
        if (!e.biometria) {
          faltantes.push('captura biométrica de referencia');
        } else if (e.biometria.vigencia === 'caducada') {
          faltantes.push('renovación de la referencia biométrica (caducada)');
          codigo = 'biometria_caducada';
        } else if (e.biometria.vigencia === 'renovacion_requerida') {
          faltantes.push('renovación de la referencia biométrica (requerida por deriva)');
          codigo = 'biometria_renovacion_requerida';
        }
      }

      // C-63: si hay vía alternativa pendiente en el perfil, mostrar ese código
      if (estadoAltPerfil === 'pendiente_proctor') {
        return {
          puede: false,
          codigo: 'via_alternativa_pendiente',
          razon: 'Tu verificación alternativa está pendiente de aprobación de un proctor.',
        };
      }

      return {
        puede: false,
        codigo,
        razon: faltantes.length > 0
          ? `Perfil incompleto: falta ${faltantes.join(' y ')}.`
          : 'Perfil incompleto.',
      };
    }

    // El perfil completo (Capa 1) es el único gate de consentimiento. El acuse
    // por-examen se eliminó por redundante: el consentimiento de perfil ya
    // verifica y bloquea la rendición.
    return { puede: true };
  },


  /** Retorna el estado de enrollment completo del perfil (C-22). */
  async getEnrollment(): Promise<EstadoEnrollment> {
    await delay(0);
    // En modo REAL la fuente de verdad es el backend: si la DB se reseteó (tmpfs),
    // el cache local en localStorage queda mintiendo "ya hiciste todo". syncEnrollmentState
    // pisa el estado local con lo que dice el servidor en cada carga.
    return syncEnrollmentState();
  },

  // -------------------------------------------------------------------------
  // Vía alternativa — C-63
  // -------------------------------------------------------------------------

  /**
   * Registra una solicitud de vía alternativa sin biometría (C-63).
   * El alumno queda en estado pendiente_proctor hasta que un proctor habilite.
   * Retorna { estado, puede_rendir } — puede_rendir=false mientras sea pendiente.
   */
  async solicitarViaAlternativa(examId: string): Promise<{ estado: string; puede_rendir: boolean }> {
    await delay(400);
    const token = authProvider.getToken?.() ?? '';
    const resp = await fetch(`${API_BASE}/consent/alternative`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ exam_id: examId }),
    });
    if (!resp.ok) throw new Error(`solicitarViaAlternativa: ${resp.status}`);
    return resp.json();
  },

  /**
   * Consulta el estado actual de la solicitud de vía alternativa (C-63).
   * Retorna { estado } si existe, null si no hay solicitud.
   */
  async estadoViaAlternativa(examId: string): Promise<{ estado: string } | null> {
    await delay(150);
    const token = authProvider.getToken?.() ?? '';
    const resp = await fetch(`${API_BASE}/consent/gate?exam_id=${encodeURIComponent(examId)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    if (
      data.resolucion === 'via_alternativa_pendiente' ||
      data.resolucion === 'via_alternativa_habilitada'
    ) {
      return { estado: data.resolucion };
    }
    return null;
  },

  /**
   * Persiste la referencia biométrica capturada en el enrollment del perfil (C-56).
   *
   * C-56: cuando USE_REAL_BACKEND=1, llama a POST /api/v1/enrollment/embedding-referencia
   * con el array de 128 floats. El backend lo cifra at-rest con Fernet y devuelve
   * un `referencia_id` opaco. El store persiste el `referencia_id` (no el embedding crudo).
   *
   * DATOS SENSIBLES (Ley 25.326):
   * - `embedding`: cifrado at-rest server-side (Fernet/AES-128-CBC + HMAC-SHA256).
   *   Finalidad acotada a verificación de identidad 1:1.
   *   Marcado para eliminación al egreso; holds legales difieren.
   * El cliente es SENSOR NO CONFIABLE: el backend re-infiere y firma (C-12).
   * D3 (C-56): el backend acepta el embedding client-side (NO re-infiere en enrollment).
   * La re-inferencia aplica durante el examen (C-09 D2).
   */
  async guardarReferenciaBiometrica(params: {
    imagen: string | null;
    embedding: number[] | null;
  }): Promise<ReferenciasBiometrica & { referencia_id?: string }> {
    // En modo real exigimos un embedding 128-d válido. Si face-api no detectó
    // rostro y devolvió null (o length distinto), antes el código caía al
    // bloque demo de abajo y NO posteaba al backend: el usuario veía "Referencia
    // capturada" pero el servidor nunca la recibía → luego en el examen
    // estadoReferenciaBiometrica devolvía false y aparecía "no enrolado".
    // Ahora fallamos fuerte para que la UI muestre error y el alumno reintente.
    if (!params.embedding || params.embedding.length !== 128) {
        throw new Error(
          'No se pudo extraer el descriptor facial de la captura. ' +
            'Asegurate de que tu rostro esté bien encuadrado, con buena luz, ' +
            'y reintentá la captura.',
        );
      }
      try {
        const data = await realFetch<{ referencia_id: string }>(
          '/enrollment/embedding-referencia',
          {
            method: 'POST',
            body: JSON.stringify({ embedding: params.embedding }),
          },
        );
        // Construir la referencia con el referencia_id opaco del backend.
        const ahora = new Date().toISOString();
        const expiracion = calcularExpiracion(ahora, BIOMETRIC_VALIDITY_MONTHS);
        const ref: ReferenciasBiometrica & { referencia_id?: string } = {
          captura_completada: true,
          imagen: null,          // C-56: el embedding se persiste en el backend, no la imagen
          embedding: null,       // C-56: el embedding crudo NO se persiste en el cliente
          fecha_captura: ahora,
          fecha_expiracion: expiracion,
          vigencia_meses: BIOMETRIC_VALIDITY_MONTHS,
          version_motor: VISION_ENGINE_VERSION,
          vigencia: calcularVigencia(expiracion, false),
          renovacion_anticipada_requerida: false,
          referencia_id: data.referencia_id,
        };
        commitEnrollment({ ...enrollmentAlumno, biometria: ref });
        return ref;
      } catch (err) {
        // Si el backend falla, NO hacer fallback demo: propagar el error
        // para que el componente pueda mostrar el mensaje y reintentar.
        const msg = err instanceof Error ? err.message : String(err);
        // 401 = token vencido (sesión larga). Mensaje claro y accionable.
        if (/\b401\b/.test(msg) || /unauthorized/i.test(msg)) {
          throw new Error('Tu sesión expiró. Cerrá sesión y volvé a iniciar sesión, y reintentá la captura.');
        }
        throw new Error(`No se pudo guardar la referencia: ${msg}`);
      }
  },

  /**
   * Guarda el escaneo de DNI como dato sensible (demo) — C-22.
   * Solo activo si ENABLE_DNI_SCAN === true. No bloquea el perfil completo.
   *
   * DATO SENSIBLE (Ley 25.326):
   * Server-side: cifrado AES-256-GCM, finalidad acotada a verificación de identidad,
   * eliminado al egreso, holds legales difieren la eliminación.
   */
  async guardarEscaneDNI(frente: string, dorso: string): Promise<EscaneDNI> {
    await delay(400);
    const escan: EscaneDNI = {
      captura_completada: true,
      imagen_frente: frente,
      imagen_dorso: dorso,
      fecha_captura: new Date().toISOString(),
    };
    commitEnrollment({ ...enrollmentAlumno, dni: escan });
    return escan;
  },

  /**
   * Simula la deriva del embedding y marca la referencia para renovación anticipada.
   * En producción este flag lo setea el backend tras detectar deriva sostenida en la
   * verificación silenciosa continua. La deriva NO sanciona ni invalida la rendición
   * en curso (L2.5 — decisión disciplinaria siempre humana).
   */
  async simularDerivaEmbedding(): Promise<void> {
    await delay(200);
    if (!enrollmentAlumno.biometria) return;
    const bioActualizada: ReferenciasBiometrica = {
      ...enrollmentAlumno.biometria,
      renovacion_anticipada_requerida: true,
      vigencia: 'renovacion_requerida',
    };
    commitEnrollment({ ...enrollmentAlumno, biometria: bioActualizada });
  },

  /** Elimina la referencia biométrica para forzar renovación (demo / testing). */
  async resetearReferenciaBiometrica(): Promise<void> {
    await delay(150);
    commitEnrollment({ ...enrollmentAlumno, biometria: null });
  },

  /**
   * Persiste la foto de perfil del alumno (C-56).
   *
   * C-56: cuando USE_REAL_BACKEND=1, llama a POST /api/v1/enrollment/foto-perfil
   * con la imagen en base64. El backend la sube al bucket no-WORM (SSE-S3), calcula
   * el hash SHA-256, persiste los metadatos en foto_referencia y devuelve el
   * `foto_referencia_id` opaco. El store persiste el ID (no el dataUrl completo).
   *
   * DATO PERSONAL (Ley 25.326): finalidad acotada (identidad en enrollment).
   * Cifrado at-rest server-side, eliminado al egreso del estudiante.
   * Demo: solo en memoria de la sesión.
   *
   * @returns foto_referencia_id (UUID opaco) en modo real, undefined en demo.
   */
  async guardarFotoPerfil(dataUrl: string): Promise<string | undefined> {
    try {
      const data = await realFetch<{ foto_referencia_id: string }>(
        '/enrollment/foto-perfil',
        {
          method: 'POST',
          body: JSON.stringify({ imagen_base64: dataUrl }),
        },
      );
      // El dataUrl no se persiste en el store (solo el ID opaco).
      return data.foto_referencia_id;
    } catch (err) {
      // Propagar el error para que el componente pueda mostrar el mensaje y reintentar.
      throw new Error(`Error al guardar foto de perfil: ${err instanceof Error ? err.message : String(err)}`);
    }
  },

  // -------------------------------------------------------------------------
  // Backend slim de proctoring — C-46
  // Todos los métodos llaman al backend slim C-45.
  // -------------------------------------------------------------------------

  /**
   * Crea una sesión de proctoring en el backend slim (C-46).
   * Real: POST /proctoring/sessions
   */
  async crearSesionProctoring(
    modo: string,
    etiqueta?: string,
    examId?: string,
    examenContenidoId?: string | null,
  ): Promise<{ id: string; creada_en: string; examen_contenido_id?: string | null }> {
    // C-69: enviamos examen_contenido_id para que la sesión REGISTRE server-side
    // contra qué examen de contenido (Moodle XML) rinde el alumno. NULLABLE: una
    // sesión de prueba (sin contenido) sigue siendo válida.
    return await realFetch<{ id: string; creada_en: string; examen_contenido_id?: string | null }>(
      '/proctoring/sessions',
      {
        method: 'POST',
        body: JSON.stringify({
          modo,
          etiqueta,
          exam_id: examId,
          examen_contenido_id: examenContenidoId ?? null,
        }),
      },
      'demo',
    );
  },

  /**
   * Envía un evento con screenshot al backend slim (C-46).
   * Real: POST /proctoring/sessions/{sessionId}/events
   * Mock o fallo: retorna null sin propagar (fire-and-forget seguro)
   *
   * DATO SENSIBLE (Ley 25.326): screenshot_base64 — se transmite solo al backend;
   * nunca se loguea ni se persiste en almacenamiento local.
   */
  async enviarEventoProctoring(
    sessionId: string,
    payload: {
      tipo: string;
      severidad: string;
      ts_cliente: string;
      payload?: Record<string, unknown>;
      screenshot_base64?: string | null;
      face_count_cliente?: number | null;
    },
  ): Promise<{
    evento_id: string;
    veredicto_reinferencia: VeredictoReinferencia;
    face_count_servidor: number;
    screenshot_sha256: string;
  } | null> {
    // El backend usa severidad en masculino (bajo|medio|alto|critico); el frontend
    // la maneja en femenino (baja|media|alta|critica) + baseline. Sin este mapeo el
    // POST da 422 y el evento se pierde en silencio (parece "sin red"/mock).
    const SEVERIDAD_BACKEND: Record<string, string> = {
      baseline: 'bajo', baja: 'bajo', media: 'medio', alta: 'alto', critica: 'critico',
    };
    const body = { ...payload, severidad: SEVERIDAD_BACKEND[payload.severidad] ?? payload.severidad };
    try {
      return await realFetch<{
        evento_id: string;
        veredicto_reinferencia: VeredictoReinferencia;
        face_count_servidor: number;
        screenshot_sha256: string;
      }>(
        `/proctoring/sessions/${sessionId}/events`,
        { method: 'POST', body: JSON.stringify(body) },
        'demo',
      );
    } catch {
      return null;
    }
  },

  /**
   * Envía el resultado de la verificación biométrica al backend slim (C-46).
   * Real: POST /proctoring/sessions/{sessionId}/biometria
   * Mock o fallo: retorna { ok: true } con delay 150ms (fire-and-forget)
   */
  async enviarBiometriaProctoring(
    sessionId: string,
    bio: {
      liveness_ok: boolean;
      retos_resueltos: string[];
      embedding?: number[];
      resultado: string;
    },
  ): Promise<{ ok: boolean }> {
    try {
      // El backend espera `embedding` como STRING (columna Text, dato sensible).
      // El cliente lo arma como number[] → serializamos a JSON string. Sin esto el
      // backend devolvía 422 y la verificación biométrica NO se guardaba en la sesión.
      const payload = {
        liveness_ok: bio.liveness_ok,
        retos_resueltos: bio.retos_resueltos,
        resultado: bio.resultado,
        ...(bio.embedding !== undefined ? { embedding: JSON.stringify(bio.embedding) } : {}),
      };
      return await realFetch<{ ok: boolean }>(
        `/proctoring/sessions/${sessionId}/biometria`,
        { method: 'POST', body: JSON.stringify(payload) },
        'demo',
      );
    } catch {
      return { ok: true };
    }
  },

  /**
   * Finaliza una sesión de proctoring (C-64).
   * Real: PATCH /proctoring/sessions/{sessionId}/finalizar
   * Mock o fallo: retorna null sin propagar (fire-and-forget seguro).
   */
  async finalizarSesionProctoring(
    sessionId: string,
  ): Promise<{ id: string; finalizada_en: string } | null> {
    if (!sessionId) return null;
    try {
      return await realFetch<{ id: string; finalizada_en: string }>(
        `/proctoring/sessions/${sessionId}/finalizar`,
        { method: 'PATCH' },
        'demo',
      );
    } catch {
      return null;
    }
  },

  /**
   * Envía las respuestas del alumno ANTES de finalizar la sesión (C-69 sección 7).
   * El backend calcula la nota server-side a partir de estas respuestas (D8: la
   * corrección y el write-back los origina el backend, nunca el cliente; D3: la
   * opción correcta nunca viaja al cliente).
   *
   * Real: POST /proctoring/sessions/{sessionId}/respuestas
   * Mock o fallo: retorna null sin propagar (degradación silenciosa — NUNCA rompe
   * el cierre del examen). El caller DEBE await-earla antes de finalizar para que
   * la nota pueda computarse, pero un error de red no debe bloquear la entrega.
   *
   * `identidad` (alumno_idnumber/email) es opcional: alimenta el write-back a Moodle
   * (D9). Si se omite, el backend usa la identidad del JWT.
   */
  async enviarRespuestasProctoring(
    sessionId: string,
    respuestas: { pregunta_id: string; opcion_elegida_id: string }[],
  ): Promise<{ session_id: string; respuestas_guardadas: number } | null> {
    if (!sessionId) return null;
    try {
      // H4 (seguridad): NO se envía identidad del cliente. El backend usa la
      // identidad del alumno persistida server-side al crear la sesión (JWT);
      // SubmitRespuestasIn rechaza (extra='forbid') cualquier campo extra.
      const body = { respuestas };
      return await realFetch<{ session_id: string; respuestas_guardadas: number }>(
        `/proctoring/sessions/${sessionId}/respuestas`,
        { method: 'POST', body: JSON.stringify(body) },
        'demo',
      );
    } catch (e) {
      // C-72 sección 7: los rechazos de PLAZO se PROPAGAN para que el alumno vea el
      // mensaje (nunca pérdida silenciosa). Otros errores (red, mock) degradan a null
      // para no romper el cierre del examen.
      const code = (e as { code?: string })?.code;
      if (code === 'tiempo_agotado' || code === 'sesion_finalizada') throw e;
      return null;
    }
  },

  /**
   * Obtiene las respuestas YA guardadas de una sesión (vuln reload/restart).
   *
   * Al reanudar una sesión ACTIVA (el backend devuelve la misma sesión ante un
   * reload, en vez de crear una zombie), el cliente usa esto para restaurar el
   * estado `respuestas` de Examen.tsx en vez de volver a arrancar en blanco.
   *
   * Real: GET /proctoring/sessions/{sessionId}/respuestas
   * Mock o fallo: retorna [] (degradación silenciosa — no bloquea el examen;
   * en el peor caso el alumno re-contesta lo que ya había contestado).
   */
  async obtenerRespuestasProctoring(
    sessionId: string,
  ): Promise<{ pregunta_id: string; opcion_elegida_id: string }[]> {
    if (!sessionId) return [];
    try {
      const data = await realFetch<{
        session_id: string;
        respuestas: { pregunta_id: string; opcion_elegida_id: string }[];
      }>(`/proctoring/sessions/${sessionId}/respuestas`, { method: 'GET' }, 'demo');
      return data.respuestas;
    } catch {
      return [];
    }
  },

  /**
   * Obtiene el detalle de una sesión de proctoring (C-64).
   * Real: GET /proctoring/sessions/{sessionId}
   * Mock o fallo: retorna null sin propagar.
   * Alias conveniente de getSesionProctoring para uso desde Cierre.tsx.
   */
  async obtenerSesionProctoring(
    sessionId: string,
  ): Promise<SesionProctoringDetalle | null> {
    if (!sessionId) return null;
    try {
      return await realFetch<SesionProctoringDetalle>(
        `/proctoring/sessions/${sessionId}`,
        { method: 'GET' },
        'demo',
      );
    } catch {
      return null;
    }
  },

  /**
   * Lista todas las sesiones de proctoring del backend slim (C-46).
   * Real: GET /proctoring/sessions
   */
  async listarSesionesProctoring(): Promise<SesionProctoringResumen[]> {
    try {
      return await realFetch<SesionProctoringResumen[]>(
        '/proctoring/sessions',
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-15 — Chat bidireccional proctor↔alumno
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Envía un mensaje al canal de chat de una sesión (C-15).
   * Real: POST /proctoring/sessions/{id}/chat → 201 {id, autor, texto, creado_en}
   * Mock o fallo: agrega a la lista en memoria y devuelve el mensaje.
   */
  async enviarMensajeChat(
    sessionId: string,
    autor: AutorChat,
    texto: string,
  ): Promise<MensajeChat> {
    return await realFetch<MensajeChat>(
      `/proctoring/sessions/${sessionId}/chat`,
      { method: 'POST', body: JSON.stringify({ autor, texto }) },
      'demo',
    );
  },

  /**
   * Lista los mensajes de chat de una sesión, asc por creado_en (C-15).
   * `desde` (ISO) → polling incremental: solo mensajes con creado_en > desde.
   * Real: GET /proctoring/sessions/{id}/chat?desde=<iso>
   * Mock o fallo: filtra la lista en memoria.
   */
  async listarMensajesChat(sessionId: string, desde?: string): Promise<MensajeChat[]> {
    try {
      const qs = desde ? `?desde=${encodeURIComponent(desde)}` : '';
      return await realFetch<MensajeChat[]>(
        `/proctoring/sessions/${sessionId}/chat${qs}`,
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-15 — Pausa autorizada
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * El alumno solicita una pausa (C-15).
   * Real: POST /proctoring/sessions/{id}/pausas → 201 pausa 'solicitada'
   * Mock o fallo: crea la pausa en memoria.
   */
  async solicitarPausa(sessionId: string, motivo: string): Promise<Pausa> {
    return await realFetch<Pausa>(
      `/proctoring/sessions/${sessionId}/pausas`,
      { method: 'POST', body: JSON.stringify({ motivo }) },
      'demo',
    );
  },

  /**
   * Lista las pausas de una sesión, desc por solicitada_en (C-15).
   * La más reciente queda primera (lo que el poll del alumno necesita).
   * Real: GET /proctoring/sessions/{id}/pausas
   * Mock o fallo: lista en memoria ordenada desc.
   */
  async listarPausas(sessionId: string): Promise<Pausa[]> {
    try {
      return await realFetch<Pausa[]>(
        `/proctoring/sessions/${sessionId}/pausas`,
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  /**
   * Lista las pausas pendientes de TODAS las sesiones (C-15) — poll del proctor.
   * Solo estado 'solicitada', asc por solicitada_en.
   * Real: GET /proctoring/pausas/pendientes
   * Mock o fallo: arma la cola desde el estado en memoria.
   */
  async listarPausasPendientes(): Promise<PausaPendiente[]> {
    try {
      return await realFetch<PausaPendiente[]>(
        '/proctoring/pausas/pendientes',
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  /**
   * El proctor resuelve una pausa solicitada: aprobar o rechazar (C-15).
   * Real: PATCH /proctoring/pausas/{id} → 200 pausa actualizada; 409 si ya no
   *       está 'solicitada' (otra resolución ganó la carrera).
   * Mock o fallo: muta la pausa en memoria; lanza Error con .status=409 si ya
   *       no estaba 'solicitada' para que la UI maneje el caso igual que en real.
   */
  async resolverPausa(
    pausaId: string,
    accion: AccionPausa,
    proctorActor?: string | null,
    motivoRechazo?: string | null,
  ): Promise<Pausa> {
    // El motivo solo viaja al rechazar (al aprobar el backend lo ignora/None).
    const body: Record<string, unknown> = {
      accion,
      proctor_actor: proctorActor ?? null,
    };
    if (accion === 'rechazar') body.motivo_rechazo = motivoRechazo ?? null;
    return await realFetch<Pausa>(
      `/proctoring/pausas/${pausaId}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      'demo',
    );
  },

  /**
   * Finaliza una pausa aprobada (el alumno reanuda el examen) (C-15).
   * Real: PATCH /proctoring/pausas/{id}/finalizar → 200 pausa 'finalizada';
   *       409 si no estaba 'aprobada'.
   * Mock o fallo: muta la pausa en memoria.
   */
  async finalizarPausa(pausaId: string): Promise<Pausa> {
    return await realFetch<Pausa>(
      `/proctoring/pausas/${pausaId}/finalizar`,
      { method: 'PATCH' },
      'demo',
    );
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-15 (3.2 / 3.3) — Acciones del proctor: observaciones + cierre forzado
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * El proctor registra una observación sobre la sesión (C-15 3.2) — insumo de C-16.
   * Real: POST /proctoring/sessions/{id}/observaciones → 201
   * Mock o fallo: agrega la observación en memoria.
   */
  async crearObservacionProctor(
    sessionId: string,
    texto: string,
    proctorActor?: string | null,
  ): Promise<ObservacionProctor> {
    return await realFetch<ObservacionProctor>(
      `/proctoring/sessions/${sessionId}/observaciones`,
      { method: 'POST', body: JSON.stringify({ texto, proctor_actor: proctorActor ?? null }) },
      'demo',
    );
  },

  /**
   * Lista las observaciones del proctor de una sesión, asc por creada_en (C-15 3.2).
   * Real: GET /proctoring/sessions/{id}/observaciones
   * Mock o fallo: lista en memoria.
   */
  async listarObservacionesProctor(sessionId: string): Promise<ObservacionProctor[]> {
    try {
      return await realFetch<ObservacionProctor[]>(
        `/proctoring/sessions/${sessionId}/observaciones`,
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  /**
   * Cierre FORZADO de una sesión por el proctor (C-15 3.3). Operativo, NO
   * disciplinario (L2.5). Idempotente: preserva el audit del primer cierre.
   * Real: PATCH /proctoring/sessions/{id}/cerrar-forzado → 200
   * Mock o fallo: simula el cierre.
   */
  async cerrarSesionForzado(
    sessionId: string,
    motivo: string,
    proctorActor?: string | null,
  ): Promise<CierreForzado> {
    return await realFetch<CierreForzado>(
      `/proctoring/sessions/${sessionId}/cerrar-forzado`,
      { method: 'PATCH', body: JSON.stringify({ motivo, proctor_actor: proctorActor ?? null }) },
      'demo',
    );
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-71 slice 2 — Decisión del revisor (dos fases). El sistema NUNCA sanciona
  // automáticamente (L2.5, regla #5): estos endpoints registran el juicio humano
  // de forma INMUTABLE (RN-RV-07). Un segundo intento devuelve 409.
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Registra la decisión de REVISIÓN (fase 1) sobre una sesión (capacidad `revisar_sesion`).
   * Real: POST /review/session/{id}/decide → 200; 409 si ya había decisión (inmutable).
   * El `motivo` viaja como `observaciones`: el fundamento queda en el audit inmutable.
   * `caso_abierto` deriva a la fase 2 (no valida ni anula la nota).
   */
  async decidirRevision(
    sessionId: string,
    decision: DecisionRevision,
    motivo: string,
  ): Promise<{ session_id: string; previous: string; new: string; actor: string; decision_at: string }> {
    return await realFetch(
      `/review/session/${sessionId}/decide`,
      { method: 'POST', body: JSON.stringify({ decision, observaciones: motivo }) },
    );
  },

  /**
   * Registra el VEREDICTO de resolución (fase 2) de un caso abierto (capacidad `resolver_caso`).
   * Real: POST /review/session/{id}/resolve → 200; 409 si ya resuelto o el caso no está abierto.
   * `motivo` obligatorio; `evidenciaRef` obligatorio si `anulado_por_fraude` (D11).
   */
  async resolverCaso(
    sessionId: string,
    resolucion: DecisionResolucion,
    motivo: string,
    evidenciaRef?: string,
  ): Promise<{ session_id: string; resolucion: string; actor: string; resolucion_at: string; nota_anulada: boolean }> {
    return await realFetch(
      `/review/session/${sessionId}/resolve`,
      {
        method: 'POST',
        body: JSON.stringify({ resolucion, motivo, evidencia_ref: evidenciaRef ?? null }),
      },
    );
  },

  /**
   * Obtiene el detalle completo de una sesión de proctoring (C-46).
   * Real: GET /proctoring/sessions/{id}
   *
   * DATO SENSIBLE (Ley 25.326): screenshot_base64 en los eventos — no loguear.
   */
  async getSesionProctoring(id: string): Promise<SesionProctoringDetalle> {
    return await realFetch<SesionProctoringDetalle>(
      `/proctoring/sessions/${id}`,
      { method: 'GET' },
      'demo',
    );
  },

  /**
   * Elimina una sesión de proctoring (C-46). Real: DELETE /proctoring/sessions/{id} (204).
   * Fallo de red: retorna { ok:false } sin romper.
   */
  async eliminarSesionProctoring(id: string): Promise<{ ok: boolean }> {
    try {
      const token = authProvider.getToken();
      const res = await fetch(`${API_BASE}/proctoring/sessions/${id}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      return { ok: res.ok };
    } catch {
      return { ok: false };
    }
  },

  // -------------------------------------------------------------------------
  // Foto de perfil — C-61 (task 5.1)
  // -------------------------------------------------------------------------

  /**
   * Obtiene la foto de perfil del usuario autenticado (C-61).
   * Real: GET /enrollment/foto-perfil → { imagen_base64: string }
   * Mock: retorna null (sin foto demo).
   */
  async obtenerFotoPerfil(): Promise<string | null> {
    try {
      const data = await realFetch<{ imagen_base64: string }>(
        '/enrollment/foto-perfil',
        { method: 'GET' },
      );
      return data.imagen_base64;
    } catch {
      return null;
    }
  },

  /**
   * Obtiene la foto de perfil de un usuario específico (admin/proctor) — C-61.
   * Real: GET /enrollment/foto-perfil/{usuario_id} → { imagen_base64: string }
   * Mock: retorna null.
   */
  async obtenerFotoPerfilDeUsuario(usuarioId: string): Promise<string | null> {
    try {
      const data = await realFetch<{ imagen_base64: string }>(
        `/enrollment/foto-perfil/${usuarioId}`,
        { method: 'GET' },
      );
      return data.imagen_base64;
    } catch {
      return null;
    }
  },

  // -------------------------------------------------------------------------
  // Gestión de usuarios (admin) — C-61 (task 6.4)
  // -------------------------------------------------------------------------

  /**
   * Lista usuarios paginados con filtros server-side (admin_sistema) — C-61 / C-68.
   * Real: GET /users/?rol=&estado=&q=&limit=&offset=
   * Mock: lista demo de 4 usuarios (activos e inactivos) con filtrado local.
   */
  async listarUsuarios(
    limit = 20,
    offset = 0,
    filtros?: { rol?: string; estado?: string; q?: string },
  ): Promise<ListarUsuariosResponse> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (filtros?.rol) params.set('rol', filtros.rol);
    if (filtros?.estado) params.set('estado', filtros.estado);
    if (filtros?.q) params.set('q', filtros.q);
    return await realFetch<ListarUsuariosResponse>(
      `/users/?${params.toString()}`,
      { method: 'GET' },
    );
  },

  /**
   * Reactiva un usuario dado de baja (admin_sistema) — C-68.
   * Real: POST /users/{id}/reactivar → usuario reactivado.
   * Mock: no-op (demo sin persistencia real de baja).
   */
  async reactivarUsuario(usuarioId: string): Promise<void> {
    const token = authProvider.getToken();
    const res = await fetch(`${API_BASE}/users/${usuarioId}/reactivar`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },

  /**
   * Crea un usuario con credencial local (admin_sistema) — C-61.
   * Real: POST /users/
   */
  async crearUsuario(body: {
    id_institucional: string;
    email: string;
    password: string;
    roles: string[];
    nombre?: string;
    apellido?: string;
  }): Promise<UsuarioAdmin> {
    return await realFetch<UsuarioAdmin>(
      '/users/',
      { method: 'POST', body: JSON.stringify(body) },
    );
  },

  /**
   * Edita email, nombre, apellido o roles de un usuario (admin_sistema) — C-61.
   * Real: PUT /users/{usuarioId}
   */
  async editarUsuario(
    usuarioId: string,
    body: { email?: string; nombre?: string; apellido?: string; roles?: string[] },
  ): Promise<UsuarioAdmin> {
    return await realFetch<UsuarioAdmin>(
      `/users/${usuarioId}`,
      { method: 'PUT', body: JSON.stringify(body) },
    );
  },

  /**
   * Da de baja lógica (soft-delete) a un usuario (admin_sistema) — C-61.
   * Real: DELETE /users/{usuarioId} → 204 sin cuerpo.
   */
  async eliminarUsuario(usuarioId: string): Promise<void> {
    const token = authProvider.getToken();
    const res = await fetch(`${API_BASE}/users/${usuarioId}`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },

  // -------------------------------------------------------------------------
  // Configuracion de scoring (admin_sistema) — #9 / #10
  // -------------------------------------------------------------------------

  /**
   * Lista los pesos configurados por tipo de evento (admin_sistema).
   * Real: GET /scoring/config
   * Mock: defaults del catalogo.
   */
  /**
   * Devuelve el mapa { tipo_evento: peso } de tipos activos (cualquier usuario
   * autenticado). Lo usa scoringWeights.ts para el calculo de score en vivo.
   * Real: GET /scoring/weights
   * Mock: defaults del catalogo.
   */
  async obtenerScoringWeights(): Promise<{ weights: Record<string, number> }> {
    return await realFetch<{ weights: Record<string, number> }>('/scoring/weights', { method: 'GET' });
  },

  async listarScoringConfig(): Promise<{ items: EventoScoreConfig[] }> {
    return await realFetch<{ items: EventoScoreConfig[] }>('/scoring/config', { method: 'GET' });
  },

  /**
   * Actualiza peso / severidad / descripcion / activo de un tipo (admin_sistema).
   * Real: PATCH /scoring/config/{tipo}
   * Mock: echo con campos sobrescritos.
   */
  async editarScoringConfig(
    tipoEvento: string,
    body: { severidad?: string; peso?: number; descripcion?: string | null; activo?: boolean },
  ): Promise<EventoScoreConfig> {
    return await realFetch<EventoScoreConfig>(
      `/scoring/config/${encodeURIComponent(tipoEvento)}`,
      { method: 'PATCH', body: JSON.stringify(body) },
    );
  },

  // -------------------------------------------------------------------------
  // Detalle de usuario (admin) — C-68
  // -------------------------------------------------------------------------

  /**
   * Detalle completo de un usuario (admin_sistema) — C-68.
   * Real: GET /users/{id}
   * Mock: busca en el listado demo.
   */
  async obtenerDetalleUsuario(id: string): Promise<UsuarioAdmin & { eliminado_en?: string | null }> {
    return await realFetch<UsuarioAdmin & { eliminado_en?: string | null }>(
      `/users/${id}`,
      { method: 'GET' },
    );
  },

  /**
   * Consentimiento de perfil de un usuario específico (admin_sistema) — C-68.
   * Real: GET /users/{id}/consent-profile
   * Mock: estado simulado con datos plausibles.
   */
  async obtenerConsentimientoDeUsuario(id: string): Promise<{
    estado: 'otorgado' | 'revocado' | null;
    version_texto: string | null;
    hash_texto: string | null;
    timestamp: string | null;
  }> {
    return await realFetch<{
      estado: 'otorgado' | 'revocado' | null;
      version_texto: string | null;
      hash_texto: string | null;
      timestamp: string | null;
    }>(`/users/${id}/consent-profile`, { method: 'GET' });
  },

  /**
   * Estado de la referencia biométrica de un usuario específico (admin_sistema) — C-68.
   * Real: GET /users/{id}/biometria/referencia/estado
   * Mock: estado simulado.
   */
  async obtenerEstadoBiometriaDeUsuario(id: string): Promise<{
    tiene_referencia_vigente: boolean;
    algoritmo: string | null;
    fecha_expiracion: string | null;
    created_at: string | null;
    tiene_foto: boolean;
    foto_hash: string | null;
    foto_created_at: string | null;
  }> {
    return await realFetch<{
      tiene_referencia_vigente: boolean;
      algoritmo: string | null;
      fecha_expiracion: string | null;
      created_at: string | null;
      tiene_foto: boolean;
      foto_hash: string | null;
      foto_created_at: string | null;
    }>(`/users/${id}/biometria/referencia/estado`, { method: 'GET' });
  },

  // -------------------------------------------------------------------------
  // Registro público de estudiantes — C-61 (task 7.3)
  // -------------------------------------------------------------------------

  /**
   * Registro público de un nuevo estudiante (C-61).
   * Real: POST /auth/register → 201 sin token.
   * Mock: 201 simulado.
   */
  async registrarUsuario(body: {
    id_institucional: string;
    nombre: string;
    apellido: string;
    email: string;
    password: string;
    password_confirmacion: string;
  }): Promise<{ id: string; id_institucional: string; email: string }> {
    return await realFetch<{ id: string; id_institucional: string; email: string }>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify(body) },
    );
  },

  // -------------------------------------------------------------------------
  // Versiones del texto de consentimiento (admin) — C-68
  // -------------------------------------------------------------------------

  /**
   * Lista las versiones publicadas del texto de consentimiento (admin_sistema).
   * Real: GET /api/v1/consent/text/versions
   * Mock: devuelve la versión demo como única entrada.
   */
  async listarVersionesConsentimiento(): Promise<{ version: string; hash_texto: string }[]> {
    return await realFetch<{ version: string; hash_texto: string }[]>(
      '/consent/text/versions',
      { method: 'GET' },
    );
  },

  /**
   * Publica una nueva versión del texto de consentimiento (admin_sistema).
   * Real: POST /api/v1/consent/text/versions
   *   body: { version, bloques: [{titulo, cuerpo}] }
   *   → 200 { version, bloques, hash_texto }
   *   → 409 si la versión ya existe
   * Mock: guarda en memoria (actualiza CONSENT_TEXT para la sesión).
   *
   * La versión publicada no se activa hasta hacer PATCH /config { consent_version_vigente }.
   */
  async crearVersionConsentimiento(params: {
    version: string;
    bloques: Array<{ titulo: string; cuerpo: string }>;
  }): Promise<{ version: string; bloques: BloqueConsentimiento[]; hash_texto: string }> {
    const raw = await realFetch<unknown>(
      '/consent/text/versions',
      { method: 'POST', body: JSON.stringify(params) },
    );
    return normalizarConsentText(raw);
  },

  // -------------------------------------------------------------------------
  // Config efectiva del sistema — configuracion-sistema-funcional (ola 2)
  // -------------------------------------------------------------------------

  /**
   * Config efectiva autoritativa (pesos + umbrales + version/ETag).
   * Accesible a cualquier usuario autenticado.
   * Real: GET /api/v1/config/effective
   * Mock: DEFAULT_CONFIG + pesos hardcodeados demo.
   */
  async obtenerConfigEfectiva(): Promise<{
    version: number;
    face_absent_ms: number;
    multiple_faces_frames: number;
    gaze_deviation_threshold: number;
    gaze_sustained_ms: number;
    gaze_fixation_tolerance: number;
    umbral_cola_revision: number;
    retencion_dias_default: number;
    consent_version_vigente: string;
    detectores_activos: string[];
    scoring_weights: Record<string, number>;
    scoring_severidades: Record<string, string>;
    // C-69 admin-sync: el backend puede no enviarlos aún (en construcción). Opcionales
    // acá; el cache normaliza a `true` (degradación segura) si vienen ausentes.
    chat_habilitado?: boolean;
    pausas_habilitadas?: boolean;
    pausa_max_min?: number;
  }> {
    return await realFetch('/config/effective', { method: 'GET' });
  },

  /**
   * Edita los defaults globales de la config del sistema.
   * SOLO admin_sistema con MFA. Invalida el cache del backend.
   * Real: PATCH /api/v1/config
   * Mock: devuelve la config demo sin cambios reales.
   */
  async editarConfigSistema(body: {
    face_absent_ms?: number;
    multiple_faces_frames?: number;
    gaze_deviation_threshold?: number;
    gaze_sustained_ms?: number;
    gaze_fixation_tolerance?: number;
    umbral_cola_revision?: number;
    detectores_activos?: string[];
    retencion_dias_default?: number;
    consent_version_vigente?: string;
    // C-69 admin-sync: habilitar/deshabilitar el chat proctor↔alumno y las pausas
    // solicitadas por el alumno desde la Configuración del sistema.
    chat_habilitado?: boolean;
    pausas_habilitadas?: boolean;
    pausa_max_min?: number;
  }): Promise<{
    version: number;
    face_absent_ms: number;
    multiple_faces_frames: number;
    gaze_deviation_threshold: number;
    gaze_sustained_ms: number;
    gaze_fixation_tolerance: number;
    umbral_cola_revision: number;
    retencion_dias_default: number;
    consent_version_vigente: string;
    detectores_activos: string[];
    scoring_weights: Record<string, number>;
    chat_habilitado?: boolean;
    pausas_habilitadas?: boolean;
  }> {
    return await realFetch('/config', { method: 'PATCH', body: JSON.stringify(body) });
  },

  // -------------------------------------------------------------------------
  // Consentimiento de perfil persistido server-side — configuracion-sistema-funcional (ola 2)
  // -------------------------------------------------------------------------

  /**
   * Otorga el consentimiento de perfil (acción afirmativa explícita, RN-CO-02).
   * Real: POST /api/v1/consent/profile
   * Demo: registra localmente (no persiste server-side).
   *
   * REEMPLAZA la implementación anterior que solo guardaba en localStorage.
   */
  async registrarConsentimientoPerfil(versionTexto: string, viaAlternativa = false): Promise<AcuseConsentimiento> {
    if (!viaAlternativa) {
      // Consentimiento directo: POST al backend server-side (Ley 25.326, append-only).
      const data = await realFetch<{
        estado: string;
        version_texto: string | null;
        hash_texto: string | null;
        timestamp: string | null;
      }>('/consent/profile', {
        method: 'POST',
        body: JSON.stringify({ version_texto: versionTexto, affirmative_action: true }),
      });
      const acuse: AcuseConsentimiento = {
        version: data.version_texto ?? versionTexto,
        timestamp: data.timestamp ?? new Date().toISOString(),
        hash: data.hash_texto ? `sha256:${data.hash_texto}` : '',
        via_alternativa: false,
      };
      commitEnrollment({ ...enrollmentAlumno, consentimiento: acuse });
      return acuse;
    }
    // Demo / vía alternativa: comportamiento original (hash simulado local)
    await delay(400);
    const acuse: AcuseConsentimiento = {
      version: versionTexto,
      timestamp: new Date().toISOString(),
      hash: 'sha256:' + Math.random().toString(16).slice(2, 18),
      via_alternativa: viaAlternativa,
    };
    commitEnrollment({ ...enrollmentAlumno, consentimiento: acuse });
    return acuse;
  },

  /**
   * Estado vigente del consentimiento de perfil del usuario autenticado.
   * Real: GET /api/v1/consent/profile
   * Demo: lee el enrollment local.
   */
  async estadoConsentimientoPerfil(): Promise<{
    estado: 'otorgado' | 'revocado' | 'inexistente';
    version_texto: string | null;
    hash_texto: string | null;
    timestamp: string | null;
  }> {
    return await realFetch('/consent/profile', { method: 'GET' });
  },

  // -------------------------------------------------------------------------
  // Catálogo de exámenes de contenido importados (C-69)
  // -------------------------------------------------------------------------

  /**
   * Lista los exámenes de contenido importados desde Moodle XML (C-69).
   *
   * GET /api/v1/exam-content → [{id, titulo, cantidad_preguntas}] en orden alfabético.
   *   Cualquier principal autenticado puede consultar el catálogo.
   *   D3: es_correcta NUNCA en la respuesta.
   *
   * Degradación silenciosa: un error de red retorna [] sin propagar (lo maneja
   * listarExamenesContenidoFn).
   */
  async listarExamenesContenido(): Promise<ExamenContenidoResumen[]> {
    const { listarExamenesContenidoFn } = await import('./examContentCatalog');
    const token = authProvider.getToken();
    return listarExamenesContenidoFn(API_BASE, token);
  },

  /**
   * Revoca el consentimiento de perfil (inserta estado revocado, preserva histórico).
   * Real: POST /api/v1/consent/profile/revoke
   * Demo: simula estado revocado.
   */
  async revocarConsentimientoPerfil(): Promise<{
    estado: string;
    version_texto: string | null;
    hash_texto: string | null;
    timestamp: string | null;
  }> {
    return await realFetch('/consent/profile/revoke', { method: 'POST' });
  },
};

// Helpers de presentación
export const SEVERIDAD_LABEL: Record<Severidad, string> = {
  baseline: 'Base', baja: 'Baja', media: 'Media', alta: 'Alta', critica: 'Crítica',
};

export const TIPO_EVENTO_LABEL: Record<TipoEvento, string> = {
  rostro_ausente: 'Rostro ausente',
  multiples_rostros: 'Múltiples rostros',
  mirada_desviada_sostenida: 'Mirada desviada sostenida',
  perdida_de_foco: 'Pérdida de foco',
  cambio_pestana: 'Cambio de pestaña',
  monitor_adicional: 'Monitor adicional',
  salida_pantalla_completa: 'Salida de pantalla completa',
  copiar_pegar: 'Copiar / Pegar',
  corte_conectividad_prolongado: 'Corte de conectividad',
  // C-72: reapertura de la rendición (el alumno recargó / volvió tras ausentarse).
  recarga_pagina: 'Recarga de página',
  reanudacion_tardia: 'Reanudación tardía',
};

export type {
  EventoSesion, Materia, Comision, Inscripcion, EstadoInscripcion,
  EstadoEnrollment, AcuseConsentimiento, ReferenciasBiometrica, EscaneDNI, VigenciaReferencia,
  // C-46: tipos de proctoring (re-export desde types.ts)
  SesionProctoringResumen, SesionProctoringDetalle, EventoProctoringDetalle,
  BiometriaDetalle, VeredictoReinferencia,
  // C-15: chat + pausa autorizada (re-export desde types.ts)
  MensajeChat, AutorChat, Pausa, AccionPausa, PausaPendiente,
  // C-61: gestión de usuarios
  UsuarioAdmin, ListarUsuariosResponse,
  // #10: scoring config
  EventoScoreConfig,
};
