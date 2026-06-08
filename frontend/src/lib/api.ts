// Capa de API del MVP. Por defecto funciona en MODO DEMO (datos en memoria, sin
// backend) para poder probar el flujo completo standalone. Si se define
// VITE_API_BASE + VITE_USE_REAL_BACKEND=1, las llamadas marcadas como reales
// (consentimiento, biometría) pasan por fetch al FastAPI real.
//
// Los esquemas y enums coinciden con app/presentation/api/v1/* del backend.

import type {
  Principal, Rol, ConsentTextResponse, ConsentResponse, Examen,
  VerifyIdentityResponse, SesionEnVivo, SesionRevision, ResumenReportes,
  EventoSesion, DesafioActivo, Severidad, TipoEvento,
  Materia, Comision, Inscripcion, EstadoInscripcion,
  EstadoEnrollment, AcuseConsentimiento, BloqueConsentimiento, ReferenciasBiometrica, EscaneDNI, VigenciaReferencia,
  AcuseExamen,
  SesionProctoringResumen, SesionProctoringDetalle, EventoProctoringDetalle,
  BiometriaDetalle, VeredictoReinferencia,
  // C-61: gestión de usuarios
  UsuarioAdmin, ListarUsuariosResponse,
} from './types';
import { INSTITUTION } from '../config/institution';
import { authProvider } from './authProvider';

export const API_BASE = (import.meta.env.VITE_API_BASE as string) || '/api/v1';
export const USE_REAL_BACKEND = import.meta.env.VITE_USE_REAL_BACKEND === '1';

const delay = (ms = 350) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------------------
// Datos demo (en memoria)
// ---------------------------------------------------------------------------

const FOTOS = {
  julian: 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=200&auto=format&fit=crop&q=80',
  martina: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=200&auto=format&fit=crop&q=80',
  tomas: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&auto=format&fit=crop&q=80',
  sofia: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=200&auto=format&fit=crop&q=80',
};

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
// Portal del alumno — datos demo (C-21)
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

// 2.5 Inscripción demo del alumno: una sola, en estado `habilitado`, apuntando al
// único examen rendible (mismo examen que Login setea como `examenActivo`). Así el
// botón "Rendir" lleva al flujo de examen con ese `examenActivo` sin clutter.
let MIS_INSCRIPCIONES: Inscripcion[] = [
  {
    id: 'INS-001', examen_id: EXAMEN_RENDIBLE_ID, comision_id: 'COM-AMAT-1A',
    materia_id: 'MAT-AMAT', nombre_examen: 'Examen Final — Análisis Matemático I',
    nombre_materia: 'Análisis Matemático I', fecha: '2026-05-30T14:00:00',
    estado: 'habilitado',
  },
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
let enrollmentAlumno: EstadoEnrollment = {
  consentimiento: null,
  biometria: null,
  dni: null,
  perfil_completo: false,
};

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

/**
 * Versión del texto del acuse por-examen (independiente de la versión de perfil).
 * Un cambio en este valor re-dispara el acuse para los exámenes afectados.
 */
export const ACUSE_EXAMEN_VERSION = '2026.1';

/**
 * Alcance de monitoreo que se muestra al alumno en el paso de acuse por-examen.
 * En producción vendría de la configuración del examen (C-07).
 */
export const ALCANCE_MONITOREO: { icono: string; label: string; descripcion: string }[] = [
  { icono: 'videocam', label: 'Cámara web', descripcion: 'Video continuo para verificación de identidad y detección de presencia.' },
  { icono: 'monitor', label: 'Pantalla y foco', descripcion: 'Captura de pantalla y detección de pérdida de foco de la ventana del examen.' },
  { icono: 'tab', label: 'Pestañas del navegador', descripcion: 'Detección de cambio o apertura de nuevas pestañas durante la rendición.' },
];

/**
 * Estado en memoria de los acuses por examen del alumno.
 * Clave: examen_id. Valor: AcuseExamen inmutable (idempotente por par estudiante/examen).
 */
let ACUSES_POR_EXAMEN: Map<string, AcuseExamen> = new Map();

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

const SESIONES_VIVO: SesionEnVivo[] = [
  { id: 'SESS-00392', estudiante: 'Emiliano Cáceres', legajo: '23.491.002', estado: 'rindiendo', score: 0, anomalias: 0, ultima_senal: 'Foco activo', foto: FOTOS.julian, es_propia: true },
  { id: 'SESS-00393', estudiante: 'Martina Rossi', legajo: '25.102.894', estado: 'rindiendo', score: 72, anomalias: 4, ultima_senal: 'Mirada desviada', foto: FOTOS.martina },
  { id: 'SESS-00394', estudiante: 'Tomás Galdámez', legajo: '24.894.201', estado: 'escalado', score: 94, anomalias: 6, ultima_senal: 'Múltiples rostros', foto: FOTOS.tomas },
  { id: 'SESS-00395', estudiante: 'Sofía Álvarez', legajo: '23.951.302', estado: 'rindiendo', score: 15, anomalias: 1, ultima_senal: 'Pérdida de foco', foto: FOTOS.sofia },
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
};

export function descripcionEvento(t: TipoEvento): string { return DESC_EVENTO[t]; }

const COLA_REVISION: SesionRevision[] = [
  {
    id: 'S-93041', estudiante: 'Tomás Galdámez', legajo: '24.894.201', examen: 'Anatomía I',
    catedra: 'Cátedra B', score: 94, fecha: '30/05/2026', duracion: '42 min', foto: FOTOS.tomas,
    decision: 'pendiente',
    eventos: [
      { id: 'EV-1', tipo: 'multiples_rostros', severidad: 'alta', ts_backend: '2026-05-30T16:12:04', descripcion: DESC_EVENTO.multiples_rostros, tiene_evidencia: true, evidencia_object_key: 'clip_tomas_01.webm' },
      { id: 'EV-2', tipo: 'monitor_adicional', severidad: 'alta', ts_backend: '2026-05-30T16:15:22', descripcion: DESC_EVENTO.monitor_adicional, tiene_evidencia: true, evidencia_object_key: 'clip_tomas_02.webm' },
      { id: 'EV-3', tipo: 'perdida_de_foco', severidad: 'baja', ts_backend: '2026-05-30T16:21:40', descripcion: DESC_EVENTO.perdida_de_foco, tiene_evidencia: false },
    ],
    cadena_custodia: { hash_cliente: 'c892fa3e…', rehash_backend: 'c892fa3e…', coincide: true, firma_maestra: 'a07f…ed25', algoritmo_firma: 'Ed25519' },
  },
  {
    id: 'S-92891', estudiante: 'Martina Rossi', legajo: '25.102.894', examen: 'Anatomía I',
    catedra: 'Cátedra B', score: 72, fecha: '30/05/2026', duracion: '58 min', foto: FOTOS.martina,
    decision: 'pendiente',
    eventos: [
      { id: 'EV-4', tipo: 'mirada_desviada_sostenida', severidad: 'media', ts_backend: '2026-05-30T15:44:12', descripcion: DESC_EVENTO.mirada_desviada_sostenida, tiene_evidencia: true, evidencia_object_key: 'clip_martina_01.webm' },
      { id: 'EV-5', tipo: 'rostro_ausente', severidad: 'media', ts_backend: '2026-05-30T15:58:30', descripcion: DESC_EVENTO.rostro_ausente, tiene_evidencia: true, evidencia_object_key: 'clip_martina_02.webm' },
    ],
    cadena_custodia: { hash_cliente: 'f41b09…', rehash_backend: 'f41b09…', coincide: true, firma_maestra: 'b13c…ed25', algoritmo_firma: 'Ed25519' },
  },
];

const REPORTES: ResumenReportes = {
  examenes_totales: 24, sesiones_totales: 1284, tasa_flag: 12.4, falsos_positivos: 31.2,
  tiempo_medio_revision: '4 min 12 s',
  distribucion_severidad: [
    { severidad: 'baja', cantidad: 612 }, { severidad: 'media', cantidad: 184 },
    { severidad: 'alta', cantidad: 73 }, { severidad: 'critica', cantidad: 18 },
  ],
  tendencia_semanal: [
    { semana: 'Sem 1', flaggeadas: 28, revisadas: 25 },
    { semana: 'Sem 2', flaggeadas: 41, revisadas: 39 },
    { semana: 'Sem 3', flaggeadas: 33, revisadas: 33 },
    { semana: 'Sem 4', flaggeadas: 52, revisadas: 47 },
  ],
};

const CONSENT_TEXT: ConsentTextResponse = {
  version: '2026.1',
  hash_texto: 'sha256:9f2b…a31',
  bloques: [
    { icono: 'help', titulo: '¿Qué datos recolectamos?', cuerpo: 'Video de tu cámara y captura de pantalla durante el examen, y un embedding facial para verificar tu identidad. El embedding se trata como dato sensible bajo la Ley 25.326.' },
    { icono: 'memory', titulo: '¿Cómo se procesan?', cuerpo: 'El análisis de visión corre localmente en tu navegador (Web Worker). Solo se envían señales discretas firmadas y, ante incidencias graves, clips cortos de evidencia. El backend re-infiere y firma toda la evidencia.' },
    { icono: 'dns', titulo: '¿Dónde se almacenan?', cuerpo: 'En infraestructura self-hosted de la universidad, cifrada en reposo, con cadena de custodia criptográfica. Soberanía de datos completa.' },
    { icono: 'schedule', titulo: '¿Cuánto tiempo?', cuerpo: 'La evidencia se conserva 30 días y luego se elimina automáticamente. El embedding biométrico se elimina al egreso, salvo apelación o hold disciplinario.' },
    { icono: 'gavel', titulo: 'Tus derechos', cuerpo: 'El sistema nunca sanciona automáticamente: solo prioriza para revisión humana. Podés acceder, rectificar y solicitar la eliminación de tus datos ante la AAIP.' },
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

// ---------------------------------------------------------------------------
// API pública (modo demo). Cada método simula latencia de red.
// ---------------------------------------------------------------------------

/**
 * Distancia coseno entre dos embeddings (1 - similitud coseno). Rango [0, 2];
 * 0 = idénticos. Usada SOLO en modo mock para reproducir el contrato del backend
 * (que compara server-side). Vectores de distinta longitud o nulos → 1 (neutro).
 */
function distanciaCoseno(a: number[], b: number[]): number {
  if (!a?.length || !b?.length || a.length !== b.length) return 1;
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  if (normA === 0 || normB === 0) return 1;
  const sim = dot / (Math.sqrt(normA) * Math.sqrt(normB));
  return 1 - sim;
}

// El token sale del provider activo (authProvider.getToken()). El 3er parámetro
// legacy se ignora (los callers históricos pasaban 'demo'); se mantiene por
// compatibilidad de firma.
async function realFetch<T>(path: string, init: RequestInit, _legacyToken?: string): Promise<T> {
  const token = authProvider.getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

// El backend (app/.../consent/schemas.py) serializa `bloques` como dict[str, str]
// con las cinco claves canónicas (que/como/donde/cuanto/derechos), mientras que la
// UI consume `BloqueConsentimiento[]` (título + cuerpo + icono). Acá traducimos esa
// forma del backend a la del frontend, en el límite de la API (el dato del backend
// es no confiable: nunca debe llegar crudo a un componente que hace `.map`).
const BLOQUE_META: Record<string, { titulo: string; icono: string }> = {
  que_se_recolecta: { titulo: '¿Qué datos recolectamos?', icono: 'help' },
  como_se_recolecta: { titulo: '¿Cómo se procesan?', icono: 'memory' },
  donde_se_almacena: { titulo: '¿Dónde se almacenan?', icono: 'dns' },
  cuanto_tiempo: { titulo: '¿Cuánto tiempo?', icono: 'schedule' },
  derechos_titular: { titulo: 'Tus derechos', icono: 'gavel' },
};

/**
 * Normaliza la respuesta de `/consent/text` a la forma del frontend.
 * Acepta tanto el array ya tipado como el `dict[str, str]` del backend real
 * (orden canónico del catálogo), garantizando que `bloques` SIEMPRE sea un array.
 */
function normalizarConsentText(raw: unknown): ConsentTextResponse {
  const r = (raw ?? {}) as { version?: string; hash_texto?: string; bloques?: unknown };
  let bloques: BloqueConsentimiento[];
  if (Array.isArray(r.bloques)) {
    bloques = r.bloques as BloqueConsentimiento[];
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
  modoDemo: !USE_REAL_BACKEND,

  async login(rol: Rol): Promise<Principal> {
    await delay(450);
    return PRINCIPALES[rol];
  },

  async getConsentText(token = 'demo'): Promise<ConsentTextResponse> {
    if (USE_REAL_BACKEND) {
      // El backend devuelve `bloques` como dict[str, str]; normalizamos a array.
      try {
        const texto = normalizarConsentText(await realFetch<unknown>('/consent/text', { method: 'GET' }, token));
        // Sincronizar la versión vigente para el gate de perfil (evita falso "renovación").
        _consentVersionVigente = texto.version || _consentVersionVigente;
        return texto;
      } catch { /* fallback demo */ }
    }
    await delay(0);
    _consentVersionVigente = CONSENT_TEXT.version;
    return CONSENT_TEXT;
  },

  async recordConsent(examId: string, token = 'demo'): Promise<ConsentResponse> {
    if (USE_REAL_BACKEND) {
      try {
        return await realFetch<ConsentResponse>('/consent', {
          method: 'POST',
          body: JSON.stringify({ exam_id: examId, version_texto: CONSENT_TEXT.version, affirmative_action: true }),
        }, token);
      } catch { /* fallback */ }
    }
    await delay(400);
    return {
      id: `CONS-${Math.floor(Math.random() * 1e6).toString(36)}`,
      user_id: PRINCIPALES.estudiante.id_institucional, exam_id: examId,
      version_texto: CONSENT_TEXT.version, timestamp: new Date().toISOString(),
      hash: 'sha256:' + Math.random().toString(16).slice(2, 10),
    };
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
    if (USE_REAL_BACKEND) {
      try {
        return await realFetch<{ tiene_referencia_vigente: boolean }>(
          '/proctoring/biometria/referencia/estado',
          { method: 'GET' },
        );
      } catch {
        // Si el endpoint falla (ej. red), asumir sin referencia para no bloquear.
        return { tiene_referencia_vigente: false };
      }
    }
    // Demo: derivar del estado local de enrollment.
    const capturada = enrollmentAlumno.biometria?.captura_completada ?? false;
    return { tiene_referencia_vigente: capturada };
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
    embeddingReferencia: number[],
    umbral?: number,
  ): Promise<{ distancia: number; es_match: boolean; umbral: number } | null> {
    if (USE_REAL_BACKEND) {
      // Rama real (C-59): solo envía el embedding vivo; el backend hace el resto.
      // embeddingReferencia se ignora intencionalmente (es null en modo real, C-56).
      try {
        return await this.verificarBiometriaReferencia(embeddingVivo, umbral);
      } catch {
        return null;
      }
    }

    // Rama demo: distancia coseno local entre los descriptores 128-d.
    await delay(900);
    const u = umbral ?? 0.35;
    const distancia = distanciaCoseno(embeddingVivo, embeddingReferencia);
    return { distancia, es_match: distancia < u, umbral: u };
  },

  async verifyIdentity(_sessionId: string, distancia = 0.31): Promise<VerifyIdentityResponse> {
    await delay(900);
    const ok = distancia < 0.5;
    return {
      veredicto: ok ? 'verificado' : 'reintento',
      distancia, reintentos_restantes: ok ? 0 : 2,
      clave_sesion_emitida: ok, escalado_a_proctor: false,
    };
  },

  async listExams(): Promise<Examen[]> { await delay(300); return [...EXAMENES]; },
  async getExam(id: string): Promise<Examen | undefined> { await delay(200); return EXAMENES.find((e) => e.id === id); },
  async saveExam(exam: Examen): Promise<Examen> {
    await delay(400);
    const i = EXAMENES.findIndex((e) => e.id === exam.id);
    if (i >= 0) EXAMENES[i] = exam; else EXAMENES = [exam, ...EXAMENES];
    return exam;
  },

  async liveSessions(): Promise<SesionEnVivo[]> { await delay(250); return SESIONES_VIVO.map((s) => ({ ...s })); },

  async reviewQueue(): Promise<SesionRevision[]> {
    await delay(300);
    return COLA_REVISION.filter((s) => s.decision === 'pendiente').map((s) => ({ ...s }));
  },
  async resolveReview(id: string, decision: SesionRevision['decision']): Promise<void> {
    await delay(300);
    const s = COLA_REVISION.find((x) => x.id === id);
    if (s) s.decision = decision;
  },

  async reportes(): Promise<ResumenReportes> { await delay(350); return REPORTES; },

  // -------------------------------------------------------------------------
  // Portal del alumno — API mock (C-21)
  // -------------------------------------------------------------------------

  /** 2.7 Retorna las materias disponibles para inscripción. */
  async materiasDisponibles(): Promise<Materia[]> {
    await delay(300);
    return [...MATERIAS];
  },

  /** 2.8 Retorna las comisiones de una materia dada. */
  async comisionesDeMateria(materiaId: string): Promise<Comision[]> {
    await delay(250);
    return COMISIONES.filter((c) => c.materia_id === materiaId);
  },

  /** 2.9 Retorna los exámenes asociados a una comisión. */
  async examenesDeComision(comisionId: string): Promise<Examen[]> {
    await delay(250);
    return EXAMENES.filter((e) => e.comision_id === comisionId);
  },

  /** 2.10 Inscribe al alumno a un examen. Idempotente: retorna la inscripción existente si ya existe. */
  async inscribir(examenId: string): Promise<Inscripcion> {
    await delay(400);
    const existente = MIS_INSCRIPCIONES.find((i) => i.examen_id === examenId);
    if (existente) return { ...existente };
    const examen = EXAMENES.find((e) => e.id === examenId);
    const comision = examen?.comision_id ? COMISIONES.find((c) => c.id === examen.comision_id) : undefined;
    const materia = comision ? MATERIAS.find((m) => m.id === comision.materia_id) : undefined;
    const nueva: Inscripcion = {
      id: `INS-${Date.now().toString(36)}`,
      examen_id: examenId,
      comision_id: comision?.id ?? '',
      materia_id: materia?.id ?? '',
      nombre_examen: examen?.nombre ?? examenId,
      nombre_materia: materia?.nombre ?? '',
      fecha: examen?.inicio ?? '',
      estado: 'inscripto',
    };
    MIS_INSCRIPCIONES = [nueva, ...MIS_INSCRIPCIONES];
    return { ...nueva };
  },

  /** 2.11 Retorna las inscripciones del alumno. */
  async misInscripciones(): Promise<Inscripcion[]> {
    await delay(250);
    return [...MIS_INSCRIPCIONES];
  },

  // -------------------------------------------------------------------------
  // Enrollment biométrico del perfil — C-22
  // -------------------------------------------------------------------------

  /**
   * Gate EN CAPAS (C-26): el alumno puede rendir si:
   * 1. Perfil completo (consentimiento de perfil vigente o vía alternativa + biometría vigente) — C-22.
   * 2. Acuse por-examen presente y afirmativo para ESE examenId — C-26.
   *
   * Los códigos de C-22 se preservan intactos. El nuevo código `acuse_examen_faltante`
   * solo aparece cuando (1) pasa pero falta (2). El gate NUNCA sanciona: deriva/flaggea (L2.5).
   */
  async puedeRendir(examenId?: string): Promise<{ puede: boolean; razon?: string; codigo?: string }> {
    await delay(200);
    const e = recalcularPerfilCompleto(enrollmentAlumno);
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
        // Proctor habilitó — puede rendir sin biometría. Saltar gate de biometría.
        // Aún se verifica el acuse por-examen (capa 2).
        const acuse = ACUSES_POR_EXAMEN.get(examenId);
        if (!acuse || !acuse.afirmativo) {
          return {
            puede: false,
            codigo: 'acuse_examen_faltante',
            razon: 'Falta el acuse de consentimiento para este examen. Confirmá tu participación antes de rendir.',
          };
        }
        return { puede: true };
      }
    }
    // También verificar estado del perfil para vía alternativa habilitada (enrollment)
    const estadoAltPerfil = _estadosViaAlternativa.get('perfil');
    if (estadoAltPerfil === 'via_alternativa_habilitada' || estadoAltPerfil === 'habilitado_por_proctor') {
      // El proctor habilitó el perfil — puede rendir sin biometría (C-63 D-04)
      if (examenId) {
        const acuse = ACUSES_POR_EXAMEN.get(examenId);
        if (!acuse || !acuse.afirmativo) {
          return {
            puede: false,
            codigo: 'acuse_examen_faltante',
            razon: 'Falta el acuse de consentimiento para este examen. Confirmá tu participación antes de rendir.',
          };
        }
      }
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

    // Capa 2: acuse por-examen (C-26) — solo se evalúa si el perfil está completo
    if (examenId) {
      const acuse = ACUSES_POR_EXAMEN.get(examenId);
      if (!acuse || !acuse.afirmativo) {
        return {
          puede: false,
          codigo: 'acuse_examen_faltante',
          razon: 'Falta el acuse de consentimiento para este examen. Confirmá tu participación antes de rendir.',
        };
      }
    }

    return { puede: true };
  },

  /**
   * Registra el acuse por-examen (C-26). Idempotente por (estudiante, examen):
   * si ya existe un acuse afirmativo para ese examenId, retorna el existente sin duplicar.
   * El acuse NO captura biometría ni re-presenta el consentimiento de perfil.
   *
   * Demo: hash simulado sobre (examen_id + version + timestamp).
   * Server-side: SHA-256 firmado por clave maestra (C-12) — el cliente es sensor no confiable.
   */
  async registrarAcuseExamen(examenId: string, params: { afirmativo: boolean }): Promise<AcuseExamen> {
    await delay(350);
    // Idempotente: retorna el existente si ya hay un acuse afirmativo
    const existente = ACUSES_POR_EXAMEN.get(examenId);
    if (existente && existente.afirmativo) return { ...existente };

    const timestamp = new Date().toISOString();
    // Demo: hash simulado. Server-side: SHA-256 sobre (estudiante, examen, version,
    // alcance_monitoreo, timestamp) firmado por clave maestra (C-12).
    const hash = 'sha256:' + Math.random().toString(16).slice(2, 18);
    const acuse: AcuseExamen = {
      examen_id: examenId,
      version: ACUSE_EXAMEN_VERSION,
      timestamp,
      hash,
      afirmativo: params.afirmativo,
    };
    ACUSES_POR_EXAMEN.set(examenId, acuse);
    return { ...acuse };
  },

  /**
   * Retorna el acuse por-examen existente para ese examenId, o null si no hay.
   * Permite que las pantallas consulten el estado del acuse sin llamar a puedeRendir.
   */
  async getAcuseExamen(examenId: string): Promise<AcuseExamen | null> {
    await delay(150);
    return ACUSES_POR_EXAMEN.get(examenId) ?? null;
  },

  /** Retorna el estado de enrollment completo del perfil (C-22). */
  async getEnrollment(): Promise<EstadoEnrollment> {
    await delay(0);
    enrollmentAlumno = recalcularPerfilCompleto(enrollmentAlumno);
    return { ...enrollmentAlumno };
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
    if (USE_REAL_BACKEND) {
      const token = authProvider.getToken?.() ?? '';
      const resp = await fetch(`${API_BASE}/consent/alternative`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ exam_id: examId }),
      });
      if (!resp.ok) throw new Error(`solicitarViaAlternativa: ${resp.status}`);
      return resp.json();
    }
    // Mock demo: guardar estado de vía alternativa pendiente
    _estadosViaAlternativa.set(examId, 'pendiente_proctor');
    return { estado: 'pendiente_proctor', puede_rendir: false };
  },

  /**
   * Consulta el estado actual de la solicitud de vía alternativa (C-63).
   * Retorna { estado } si existe, null si no hay solicitud.
   */
  async estadoViaAlternativa(examId: string): Promise<{ estado: string } | null> {
    await delay(150);
    if (USE_REAL_BACKEND) {
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
    }
    // Mock demo
    const estado = _estadosViaAlternativa.get(examId);
    return estado != null ? { estado } : null;
  },

  /**
   * Registra el acuse de consentimiento en el perfil (C-22).
   * Acción afirmativa explícita; nunca pre-marcado (RN-CO-02).
   * El acuse referencia la versión exacta del texto mostrado (RN-CO-01).
   *
   * Demo: hash simulado. Server-side: SHA-256 firmado por clave maestra (C-12).
   */
  async registrarConsentimientoPerfil(versionTexto: string, viaAlternativa = false): Promise<AcuseConsentimiento> {
    await delay(400);
    const acuse: AcuseConsentimiento = {
      version: versionTexto,
      timestamp: new Date().toISOString(),
      // Demo: hash simulado. Server-side: SHA-256 del contenido firmado server-side.
      hash: 'sha256:' + Math.random().toString(16).slice(2, 18),
      via_alternativa: viaAlternativa,
    };
    enrollmentAlumno = recalcularPerfilCompleto({ ...enrollmentAlumno, consentimiento: acuse });
    return acuse;
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
    if (USE_REAL_BACKEND) {
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
        enrollmentAlumno = recalcularPerfilCompleto({ ...enrollmentAlumno, biometria: ref });
        return ref;
      } catch (err) {
        // Si el backend falla, NO hacer fallback demo: propagar el error
        // para que el componente pueda mostrar el mensaje y reintentar.
        throw new Error(`Error al guardar referencia biométrica: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
    // Modo demo (USE_REAL_BACKEND=0 o embedding nulo/incompleto).
    await delay(600);
    const ahora = new Date().toISOString();
    const expiracion = calcularExpiracion(ahora, BIOMETRIC_VALIDITY_MONTHS);
    const ref: ReferenciasBiometrica & { referencia_id?: string } = {
      captura_completada: true,
      imagen: params.imagen,
      embedding: params.embedding,
      fecha_captura: ahora,
      fecha_expiracion: expiracion,
      vigencia_meses: BIOMETRIC_VALIDITY_MONTHS,
      version_motor: VISION_ENGINE_VERSION,
      vigencia: calcularVigencia(expiracion, false),
      renovacion_anticipada_requerida: false,
    };
    enrollmentAlumno = recalcularPerfilCompleto({ ...enrollmentAlumno, biometria: ref });
    return ref;
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
    enrollmentAlumno = recalcularPerfilCompleto({ ...enrollmentAlumno, dni: escan });
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
    enrollmentAlumno = recalcularPerfilCompleto({ ...enrollmentAlumno, biometria: bioActualizada });
  },

  /** Elimina la referencia biométrica para forzar renovación (demo / testing). */
  async resetearReferenciaBiometrica(): Promise<void> {
    await delay(150);
    enrollmentAlumno = recalcularPerfilCompleto({ ...enrollmentAlumno, biometria: null });
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
    if (USE_REAL_BACKEND) {
      try {
        const data = await realFetch<{ foto_referencia_id: string }>(
          '/enrollment/foto-perfil',
          {
            method: 'POST',
            body: JSON.stringify({ imagen_base64: dataUrl }),
          },
        );
        // En modo real el dataUrl no se persiste en el store (solo el ID opaco).
        return data.foto_referencia_id;
      } catch (err) {
        // Propagar el error para que el componente pueda mostrar el mensaje y reintentar.
        throw new Error(`Error al guardar foto de perfil: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
    // Modo demo: guardar en memoria de la sesión (sin persistencia real).
    await delay(300);
    PRINCIPALES.estudiante = { ...PRINCIPALES.estudiante, foto_perfil: dataUrl };
    return undefined;
  },

  // -------------------------------------------------------------------------
  // Backend slim de proctoring — C-46 (dual real/mock)
  // Todos los métodos: con USE_REAL_BACKEND=1 llaman al backend slim C-45;
  // con USE_REAL_BACKEND=0 (default Vercel) retornan datos mock sin HTTP.
  // -------------------------------------------------------------------------

  /**
   * Crea una sesión de proctoring en el backend slim (C-46).
   * Real: POST /proctoring/sessions
   * Mock: objeto simulado con delay 200ms
   */
  async crearSesionProctoring(
    modo: string,
    etiqueta?: string,
    examId?: string,
  ): Promise<{ id: string; creada_en: string }> {
    if (USE_REAL_BACKEND) {
      try {
        return await realFetch<{ id: string; creada_en: string }>(
          '/proctoring/sessions',
          {
            method: 'POST',
            body: JSON.stringify({ modo, etiqueta, exam_id: examId }),
          },
          'demo',
        );
      } catch {
        /* fallback mock */
      }
    }
    await delay(200);
    return { id: 'mock-session-' + Date.now(), creada_en: new Date().toISOString() };
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
    if (USE_REAL_BACKEND) {
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
    }
    // Mock: retorna null (no simula veredicto — el harness lo muestra como "sin red")
    return null;
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
    if (USE_REAL_BACKEND) {
      try {
        return await realFetch<{ ok: boolean }>(
          `/proctoring/sessions/${sessionId}/biometria`,
          { method: 'POST', body: JSON.stringify(bio) },
          'demo',
        );
      } catch {
        return { ok: true };
      }
    }
    await delay(150);
    return { ok: true };
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
    if (USE_REAL_BACKEND) {
      try {
        return await realFetch<{ id: string; finalizada_en: string }>(
          `/proctoring/sessions/${sessionId}/finalizar`,
          { method: 'PATCH' },
          'demo',
        );
      } catch {
        return null;
      }
    }
    // Mock: simular finalización exitosa
    return { id: sessionId, finalizada_en: new Date().toISOString() };
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
    if (USE_REAL_BACKEND) {
      try {
        return await realFetch<SesionProctoringDetalle>(
          `/proctoring/sessions/${sessionId}`,
          { method: 'GET' },
          'demo',
        );
      } catch {
        return null;
      }
    }
    // Mock: retorna null (Cierre.tsx usa fallback del store)
    return null;
  },

  /**
   * Lista todas las sesiones de proctoring del backend slim (C-46).
   * Real: GET /proctoring/sessions
   * Mock: dos sesiones de ejemplo con datos plausibles
   */
  async listarSesionesProctoring(): Promise<SesionProctoringResumen[]> {
    if (USE_REAL_BACKEND) {
      try {
        return await realFetch<SesionProctoringResumen[]>(
          '/proctoring/sessions',
          { method: 'GET' },
          'demo',
        );
      } catch {
        /* fallback mock */
      }
    }
    await delay(300);
    const ahora = new Date();
    const hace1h = new Date(ahora.getTime() - 3600 * 1000).toISOString();
    const hace30m = new Date(ahora.getTime() - 1800 * 1000).toISOString();
    const hace10m = new Date(ahora.getTime() - 600 * 1000).toISOString();
    const hace5m = new Date(ahora.getTime() - 300 * 1000).toISOString();
    const hace20m = new Date(ahora.getTime() - 1200 * 1000).toISOString();
    return [
      {
        // Sesión de alto riesgo (score ≥ umbral de cola): la cola de revisión la prioriza.
        // exam_id apunta al examen real del catálogo para que el join muestre materia/comisión.
        id: 'mock-session-examen-altoriesgo-003',
        modo: 'examen',
        etiqueta: 'Persona en banca 12',
        creada_en: hace10m,
        total_eventos: 5,
        total_discrepancias: 2,
        score: 72,
        exam_id: EXAMEN_RENDIBLE_ID,
      },
      {
        // Segunda persona de alto riesgo en el mismo examen (puebla el nivel "Personas").
        id: 'mock-session-examen-altoriesgo-004',
        modo: 'examen',
        etiqueta: 'Persona en banca 04',
        creada_en: hace5m,
        total_eventos: 9,
        total_discrepancias: 4,
        score: 84,
        exam_id: EXAMEN_RENDIBLE_ID,
      },
      {
        // Tercera persona de alto riesgo en el mismo examen.
        id: 'mock-session-examen-altoriesgo-005',
        modo: 'examen',
        etiqueta: 'Persona en banca 21',
        creada_en: hace20m,
        total_eventos: 4,
        total_discrepancias: 1,
        score: 67,
        exam_id: EXAMEN_RENDIBLE_ID,
      },
      {
        id: 'mock-session-diagnostico-001',
        modo: 'diagnostico',
        etiqueta: 'Prueba de detección local',
        creada_en: hace1h,
        total_eventos: 7,
        total_discrepancias: 2,
        score: 38,
      },
      {
        id: 'mock-session-examen-002',
        modo: 'examen',
        etiqueta: 'Persona en banca 08',
        creada_en: hace30m,
        total_eventos: 3,
        total_discrepancias: 0,
        score: 12,
        exam_id: EXAMEN_RENDIBLE_ID,
      },
    ];
  },

  /**
   * Obtiene el detalle completo de una sesión de proctoring (C-46).
   * Real: GET /proctoring/sessions/{id}
   * Mock: sesión con eventos variados, veredictos y biometría simulada
   *
   * DATO SENSIBLE (Ley 25.326): screenshot_base64 en los eventos — no loguear.
   */
  async getSesionProctoring(id: string): Promise<SesionProctoringDetalle> {
    if (USE_REAL_BACKEND) {
      try {
        return await realFetch<SesionProctoringDetalle>(
          `/proctoring/sessions/${id}`,
          { method: 'GET' },
          'demo',
        );
      } catch {
        /* fallback mock */
      }
    }
    await delay(300);
    const ahora = new Date();
    return {
      id,
      modo: 'diagnostico',
      etiqueta: 'Prueba de detección local',
      creada_en: new Date(ahora.getTime() - 3600 * 1000).toISOString(),
      total_eventos: 3,
      total_discrepancias: 1,
      score: 38,
      eventos: [
        {
          evento_id: 'ev-mock-001',
          tipo: 'multiples_rostros',
          severidad: 'alta',
          ts_cliente: new Date(ahora.getTime() - 3000 * 1000).toISOString(),
          payload: { face_count: 2 },
          screenshot_base64: null, // mock no incluye imagen real
          screenshot_sha256: null,
          face_count_cliente: 2,
          veredicto_reinferencia: 'coincide',
          face_count_servidor: 2,
        },
        {
          evento_id: 'ev-mock-002',
          tipo: 'mirada_desviada_sostenida',
          severidad: 'media',
          ts_cliente: new Date(ahora.getTime() - 2500 * 1000).toISOString(),
          payload: { sostenido_ms: 2600 },
          screenshot_base64: null,
          screenshot_sha256: null,
          face_count_cliente: 1,
          veredicto_reinferencia: 'discrepancia',
          face_count_servidor: 0,
        },
        {
          evento_id: 'ev-mock-003',
          tipo: 'rostro_ausente',
          severidad: 'media',
          ts_cliente: new Date(ahora.getTime() - 1800 * 1000).toISOString(),
          payload: { sostenido_ms: 3200 },
          screenshot_base64: null,
          screenshot_sha256: null,
          face_count_cliente: 0,
          veredicto_reinferencia: 'sin_referencia',
          face_count_servidor: 0,
        },
      ],
      biometria: {
        liveness_ok: true,
        retos_resueltos: ['parpadear', 'girar_izquierda'],
        resultado: 'verificado',
      },
    };
  },

  /**
   * Elimina una sesión de proctoring (C-46). Real: DELETE /proctoring/sessions/{id} (204).
   * Mock o fallo: retorna { ok:false } sin romper.
   */
  async eliminarSesionProctoring(id: string): Promise<{ ok: boolean }> {
    if (USE_REAL_BACKEND) {
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
    }
    await delay(200);
    return { ok: true }; // mock: simula éxito
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
    if (USE_REAL_BACKEND) {
      try {
        const data = await realFetch<{ imagen_base64: string }>(
          '/enrollment/foto-perfil',
          { method: 'GET' },
        );
        return data.imagen_base64;
      } catch {
        return null;
      }
    }
    await delay(150);
    return null; // mock: sin foto
  },

  /**
   * Obtiene la foto de perfil de un usuario específico (admin/proctor) — C-61.
   * Real: GET /enrollment/foto-perfil/{usuario_id} → { imagen_base64: string }
   * Mock: retorna null.
   */
  async obtenerFotoPerfilDeUsuario(usuarioId: string): Promise<string | null> {
    if (USE_REAL_BACKEND) {
      try {
        const data = await realFetch<{ imagen_base64: string }>(
          `/enrollment/foto-perfil/${usuarioId}`,
          { method: 'GET' },
        );
        return data.imagen_base64;
      } catch {
        return null;
      }
    }
    await delay(150);
    return null; // mock: sin foto
  },

  // -------------------------------------------------------------------------
  // Gestión de usuarios (admin) — C-61 (task 6.4)
  // -------------------------------------------------------------------------

  /**
   * Lista usuarios paginados (admin_sistema) — C-61.
   * Real: GET /users/?limit=&offset=
   * Mock: lista demo de 3 usuarios.
   */
  async listarUsuarios(limit = 20, offset = 0): Promise<ListarUsuariosResponse> {
    if (USE_REAL_BACKEND) {
      return await realFetch<ListarUsuariosResponse>(
        `/users/?limit=${limit}&offset=${offset}`,
        { method: 'GET' },
      );
    }
    await delay(300);
    const items: UsuarioAdmin[] = [
      { id: 'u1', id_institucional: 'FRM-ADM-0021', email: 'lmendoza@frm.utn.edu.ar', nombre: 'Lucía', apellido: 'Mendoza', roles: ['admin_sistema'], auth_provider: 'local' },
      { id: 'u2', id_institucional: 'FRM-DOC-1182', email: 'cferreyra@frm.utn.edu.ar', nombre: 'Carolina', apellido: 'Ferreyra', roles: ['proctor'], auth_provider: 'local' },
      { id: 'u3', id_institucional: 'FRM-23-4912', email: 'ecaceres@frm.utn.edu.ar', nombre: 'Emiliano', apellido: 'Cáceres', roles: ['estudiante'], auth_provider: 'local' },
    ];
    return { items, total: items.length, limit, offset };
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
    if (USE_REAL_BACKEND) {
      return await realFetch<UsuarioAdmin>(
        '/users/',
        { method: 'POST', body: JSON.stringify(body) },
      );
    }
    await delay(400);
    return {
      id: 'u-' + Date.now().toString(36),
      id_institucional: body.id_institucional,
      email: body.email,
      nombre: body.nombre ?? null,
      apellido: body.apellido ?? null,
      roles: body.roles,
      auth_provider: 'local',
    };
  },

  /**
   * Edita email, nombre, apellido o roles de un usuario (admin_sistema) — C-61.
   * Real: PUT /users/{usuarioId}
   */
  async editarUsuario(
    usuarioId: string,
    body: { email?: string; nombre?: string; apellido?: string; roles?: string[] },
  ): Promise<UsuarioAdmin> {
    if (USE_REAL_BACKEND) {
      return await realFetch<UsuarioAdmin>(
        `/users/${usuarioId}`,
        { method: 'PUT', body: JSON.stringify(body) },
      );
    }
    await delay(350);
    return {
      id: usuarioId,
      id_institucional: '',
      email: body.email ?? '',
      nombre: body.nombre ?? null,
      apellido: body.apellido ?? null,
      roles: body.roles ?? [],
      auth_provider: 'local',
    };
  },

  /**
   * Da de baja lógica (soft-delete) a un usuario (admin_sistema) — C-61.
   * Real: DELETE /users/{usuarioId} → 204 sin cuerpo.
   */
  async eliminarUsuario(usuarioId: string): Promise<void> {
    if (USE_REAL_BACKEND) {
      const token = authProvider.getToken();
      const res = await fetch(`${API_BASE}/users/${usuarioId}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return;
    }
    await delay(300);
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
    if (USE_REAL_BACKEND) {
      return await realFetch<{ id: string; id_institucional: string; email: string }>(
        '/auth/register',
        { method: 'POST', body: JSON.stringify(body) },
      );
    }
    await delay(500);
    return {
      id: 'u-' + Date.now().toString(36),
      id_institucional: body.id_institucional,
      email: body.email,
    };
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
};

export type {
  EventoSesion, Materia, Comision, Inscripcion, EstadoInscripcion,
  EstadoEnrollment, AcuseConsentimiento, ReferenciasBiometrica, EscaneDNI, VigenciaReferencia,
  AcuseExamen,
  // C-46: tipos de proctoring (re-export desde types.ts)
  SesionProctoringResumen, SesionProctoringDetalle, EventoProctoringDetalle,
  BiometriaDetalle, VeredictoReinferencia,
  // C-61: gestión de usuarios
  UsuarioAdmin, ListarUsuariosResponse,
};
