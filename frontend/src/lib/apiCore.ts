// Capa de API del MVP. Por defecto funciona en MODO DEMO (datos en memoria, sin
// backend) para poder probar el flujo completo standalone. Si se define
// VITE_API_BASE + VITE_USE_REAL_BACKEND=1, las llamadas marcadas como reales
// (consentimiento, biometría) pasan por fetch al FastAPI real.
//
// Los esquemas y enums coinciden con app/presentation/api/v1/* del backend.

import type {
  ConsentTextResponse, DesafioActivo,
  EstadoEnrollment, AcuseConsentimiento, BloqueConsentimiento,
  ReferenciasBiometrica, VigenciaReferencia,
} from './types';
import { authProvider } from './authProvider';

export const API_BASE = (import.meta.env.VITE_API_BASE as string) || '/api/v1';

const delay = (ms = 350) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------------------
// Catálogo académico local (usado por joinExamInfo en las pantallas de proctoring)
// ---------------------------------------------------------------------------


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

// Mapas de presentación (DESC_EVENTO/descripcionEvento/SEVERIDAD_LABEL/
// TIPO_EVENTO_LABEL) movidos a ./apiLabels — se re-exportan al final del archivo
// para no romper los imports existentes desde '../lib/api'.

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

// ── Exports internos para el objeto `api` (./api) — refactor c-76 ──────────────
export {
  delay,
  VISION_ENGINE_VERSION,
  LS_ENROLLMENT,
  LS_FOTO,
  calcularExpiracion,
  calcularVigencia,
  loadEnrollmentFromLS,
  persistEnrollment,
  commitEnrollment,
  recalcularPerfilCompleto,
  _estadosViaAlternativa,
  consentVersionVigente,
  ensureConsentVersionSynced,
  syncEnrollmentState,
  realFetch,
  BLOQUE_META,
  inferirIconoBloque,
  normalizarConsentText,
  CONSENT_TEXT,
  enrollmentAlumno,
};

/** Setters del estado mutable del módulo: los ES-module bindings no se pueden
 * reasignar desde otro archivo, así que el objeto `api` muta vía estos. */
export function setEnrollmentAlumno(e: EstadoEnrollment): void {
  enrollmentAlumno = e;
}
export function setConsentVersionVigente(v: string): void {
  _consentVersionVigente = v;
}

