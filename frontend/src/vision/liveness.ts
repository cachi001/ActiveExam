/**
 * Liveness hibrido del cliente: pasivo + retos activos aleatorios (C-09, DD-18).
 *
 * Logica PURA (sin DOM ni MediaPipe) para que sea testeable y reusable. El motor
 * de vision provee los landmarks/senales; aqui se decide el gate de liveness y se
 * eligen los retos activos AL AZAR (RN-BIO-05). Es la primera capa de defensa; el
 * backend RE-INFIERE sobre el clip y decide la habilitacion (RN-GLB-01).
 *
 * Espeja el dominio del backend (``app.domain.biometrics.liveness``): mismos retos
 * y mismo criterio de exito, para que la re-inferencia server-side sea coherente.
 *
 * C-54: agrega motor de retos secuenciales (baseline neutral + evaluacion relativa).
 *
 * ── Alcance PAD honesto (C-67, ISO/IEC 30107-3, DD-18) ────────────────────────
 *
 * Este módulo implementa defensa anti-presentación (PAD) de Nivel 1–2 en el
 * navegador: protege contra fotos estáticas, videos de reproducción y máscaras
 * de mediana sofisticación. Combina tres capas:
 *   1. Reto-respuesta activo (gestos secuenciales barajados con Fisher-Yates,
 *      giro con dirección aleatoria por intento — elevan el costo del video pregrabado).
 *   2. Señales pasivas (parpadeo, micro-movimientos, profundidad 3D de 468 landmarks).
 *   3. Detección de cámara virtual / inyección de pipeline.
 *
 * LÍMITE HONESTO — NO hay inmunidad a:
 *   - Inyección de cámara (camera pipe injection): el atacante evita la cámara
 *     física e inyecta video sintético directamente en el pipeline de la app.
 *   - Deepfakes "puppet master" en tiempo real: pueden ejecutar los retos activos.
 * Ambas amenazas son límites inherentes al paradigma cliente (el cliente es
 * manipulable por definición). Ningún liveness que corra en el navegador puede
 * garantizar inmunidad a la inyección (DD-18).
 *
 * La red de seguridad REAL combina (en orden de autoridad):
 *   1. Re-inferencia server-side sobre el clip (RN-GLB-01, C-12, C-59).
 *   2. Verificación biométrica continua durante el examen.
 *   3. Revisión humana por el proctor (L2.5 — NUNCA sanción automática, RN-GLB-02).
 *
 * Las señales de este módulo se REPORTAN al backend como evidencia, no como
 * veredicto final. El cliente es SENSOR NO CONFIABLE (regla dura #6).
 */

import type { FrameResult, PassiveSignals } from "./VisionEngine";

// ---------------------------------------------------------------------------
// C-54: Catalogo secuencial de retos (Task 1.1, 1.4, 1.2, 1.3)
// ---------------------------------------------------------------------------

/**
 * Catalogo de retos secuenciales de liveness (C-54, D-4).
 * Excluye "acercarse" (falsos positivos, no estandar ISO/IEC 30107-3).
 * El orden se baraja con Fisher-Yates al iniciar cada intento.
 */
export const SEQUENTIAL_CHALLENGES = [
  "parpadear",
  "girar_cabeza",
  "sonreír",
] as const;

/** Tipo derivado del catalogo secuencial. */
export type SequentialChallenge = (typeof SEQUENTIAL_CHALLENGES)[number];

/**
 * Direccion de giro para el reto `girar_cabeza` (D-4).
 * Se elige al azar al montar el componente y permanece fija durante el intento.
 * Convencion de espejo selfie (coherente con enrollmentChallengeDetector.ts):
 * - 'izquierda' -> gaze.x > +threshold (lo que el alumno percibe como su izquierda)
 * - 'derecha'   -> gaze.x < -threshold (lo que el alumno percibe como su derecha)
 */
export type TurnDirection = "izquierda" | "derecha";

/**
 * Estado de la maquina de estados del motor de retos secuenciales (C-54, D-1).
 * - idle:      estado inicial antes de iniciar la captura
 * - baseline:  acumulando metricas neutrales del alumno (pre-retos)
 * - challenge: evaluando el reto activo (challengeIndex)
 * - cooldown:  confirmacion visual del paso completado (350 ms)
 * - done:      todos los retos completados
 */
export type ChallengeState = "idle" | "baseline" | "challenge" | "cooldown" | "done";

/**
 * Metricas neutrales del alumno capturadas durante la fase baseline (C-54, D-2).
 * Se usan como referencia para la evaluacion por delta relativo.
 *
 * @field blinkOpenness  Apertura vertical media del ojo izquierdo en reposo
 *                       (|lm[159].y - lm[145].y|). La evaluacion pide que
 *                       baje al 45 % de este valor para detectar parpadeo.
 * @field smileWidth     Ancho de boca medio en reposo (|lm[291].x - lm[61].x|).
 *                       La evaluacion pide que suba al 125 % para detectar sonrisa.
 * @field gazeX          Posicion horizontal media del iris en reposo (referencia
 *                       de frente). No se usa directamente en la evaluacion actual
 *                       (el giro usa umbral absoluto ajustado), pero se captura
 *                       para posible uso futuro.
 */
export interface BaselineMetrics {
  blinkOpenness: number;
  smileWidth: number;
  gazeX: number;
  /**
   * C-67: Posición Y promedio de las comisuras de la boca en reposo.
   * Landmarks 61 (izquierda) y 291 (derecha): avgCornerY = (lm[61].y + lm[291].y) / 2.
   * Cuando el alumno sonríe, las comisuras suben (y disminuye en coordenadas de imagen).
   * Usado por la métrica compuesta de sonrisa (elevación + ancho).
   * Opcional: undefined si el baseline se computó antes de C-67 (backward compatible).
   */
  smileCornerY?: number;
}

// ---------------------------------------------------------------------------
// Catalogo legacy (C-09) — mantenido para compatibilidad hacia atras
// ---------------------------------------------------------------------------

/**
 * Retos activos del catalogo legacy (mismos valores que el backend).
 * @deprecated Usar SEQUENTIAL_CHALLENGES para el flujo de enrollment (C-54).
 */
export const ACTIVE_CHALLENGES = [
  "girar_izquierda",
  "girar_derecha",
  "parpadear",
  "acercarse",
  "sonreir",
] as const;

export type ActiveChallenge = (typeof ACTIVE_CHALLENGES)[number];

export const MIN_ACTIVE_CHALLENGES = 1;
export const MAX_ACTIVE_CHALLENGES = 2;

/**
 * Elige 1-2 retos activos AL AZAR (RN-BIO-05). ``rng`` inyectable para tests
 * deterministas (default ``Math.random``).
 * @deprecated Usar SEQUENTIAL_CHALLENGES + barajado Fisher-Yates en BiometricCapture (C-54).
 */
export function pickActiveChallenges(
  count = 2,
  rng: () => number = Math.random,
): ActiveChallenge[] {
  const n = Math.max(MIN_ACTIVE_CHALLENGES, Math.min(MAX_ACTIVE_CHALLENGES, count));
  const pool = [...ACTIVE_CHALLENGES];
  const chosen: ActiveChallenge[] = [];
  for (let i = 0; i < n && pool.length > 0; i += 1) {
    const idx = Math.floor(rng() * pool.length);
    chosen.push(pool.splice(idx, 1)[0]);
  }
  return chosen;
}

/**
 * Deriva las senales pasivas de liveness a partir de la secuencia de frames del
 * clip. Heuristica de cliente (no fuente de verdad):
 * - parpadeo: la apertura de ojos varia entre frames (no estatica como una foto).
 * - micro-movimientos: la posicion de los landmarks varia sutilmente.
 * - profundidad 3D coherente: el rango de ``z`` indica volumen (no un plano).
 *
 * ``blinkOpenness``/``motion``/``depthRange`` se calculan del motor; aqui se
 * aplican los umbrales del cliente. Una foto/video plano da varianza ~0 y z ~0.
 *
 * Alcance PAD (ISO 30107-3 Nivel 1–2): detecta fotos y videos de baja calidad.
 * No detecta deepfakes de alta fidelidad ni inyección de cámara — esas amenazas
 * requieren re-inferencia server-side (DD-18). El resultado se REPORTA al backend;
 * NO es el veredicto final.
 */
export function derivePassiveSignals(metrics: {
  blinkVariance: number;
  motionVariance: number;
  depthRange: number;
}): PassiveSignals {
  return {
    parpadeo_detectado: metrics.blinkVariance > 0.01,
    micro_movimientos: metrics.motionVariance > 0.0005,
    profundidad_3d_coherente: metrics.depthRange > 0.02,
  };
}

/**
 * El pasivo pasa solo si las TRES senales son positivas (defensa estricta).
 *
 * Alcance honesto (ISO 30107-3, DD-18): este gate cubre Nivel 1–2 (fotos planas,
 * videos estáticos). Deepfakes puppet-master o inyección de cámara pueden tener
 * varianza suficiente para superarlo. La re-inferencia server-side es la
 * verificación autoritativa. El sistema NUNCA sanciona automáticamente (L2.5).
 */
export function passivePassed(signals: PassiveSignals): boolean {
  return (
    signals.parpadeo_detectado &&
    signals.micro_movimientos &&
    signals.profundidad_3d_coherente
  );
}

/**
 * Gate de liveness del cliente: pasivo OK + todos los retos resueltos + sin camara
 * virtual. Espeja ``liveness_exitoso`` del backend. NO es el veredicto final: el
 * backend re-infiere (RN-GLB-01).
 *
 * Alcance PAD honesto (ISO 30107-3 Nivel 1–2, DD-18):
 * - Protege contra fotos estáticas, videos de reproducción, máscaras de mediana
 *   sofisticación (nivel comercial razonable para exámenes universitarios).
 * - NO garantiza inmunidad a inyección de cámara ni a deepfakes puppet-master.
 * - La verificación autoritativa es re-inferencia server-side + verificación
 *   continua + revisión humana (L2.5, regla dura #5 y #6).
 * El resultado se reporta al backend como evidencia (`liveness_ok`, `retos_resueltos`,
 * `resultado: "camara_virtual_detectada"` | "verificado"). El cliente es sensor
 * no confiable; el backend firma y re-infiere.
 */
export function clientLivenessOk(args: {
  passive: PassiveSignals;
  requested: ActiveChallenge[];
  solved: ActiveChallenge[];
  virtualCameraDetected: boolean;
}): boolean {
  if (args.virtualCameraDetected) return false;
  if (!passivePassed(args.passive)) return false;
  const solved = new Set(args.solved);
  return args.requested.every((c) => solved.has(c));
}

/**
 * Heuristica de integridad para detectar CAMARA VIRTUAL / inyeccion de pipeline
 * (DD-18). Senales tipicas de un feed sintetico inyectado:
 * - varianza de pixeles anormalmente baja entre frames consecutivos (feed loop).
 * - ausencia total de micro-movimientos junto con face_count estable perfecto.
 * - frameRate sospechosamente constante (sin jitter de camara fisica).
 *
 * Es UNA capa, no el veredicto unico (DD-18): se REPORTA al backend.
 *
 * Límite honesto (ISO 30107-3, DD-18): detecta inyecciones simples (bucles de video,
 * feeds perfectamente estables). Un atacante sofisticado puede introducir jitter
 * artificial para evadir esta heurística. La defensa robusta contra inyección de
 * cámara es análisis server-side del contexto del OS/browser (Fase 2, DD-18).
 * Este resultado se reporta como señal de contexto (`resultado: "camara_virtual_detectada"`),
 * NO como sanción automática. La decisión disciplinaria es siempre humana (L2.5).
 */
export function detectVirtualCamera(signals: {
  interFramePixelVariance: number;
  frameRateJitter: number;
  faceCountStability: number;
  /**
   * Si la varianza de pixeles se pudo medir DE VERDAD contra un frame anterior
   * distinto. Default `true` por retrocompatibilidad con los llamadores viejos.
   *
   * Sin esto, "no pude medir" y "el feed esta en loop" llegaban acá con el mismo
   * valor (0), y como 0 es justo lo que dispara la sospecha, un fallo de medicion
   * quedaba registrado como fraude en el legajo del alumno. Pasa por dos caminos
   * normales: el canvas bloqueado (el `catch` dejaba 0), y leer dos veces el
   * MISMO frame de camara, que es lo habitual cuando el loop corre a 60 Hz contra
   * una webcam de 30 fps — comparar un frame consigo mismo da diferencia cero.
   */
  medicionValida?: boolean;
}): boolean {
  // Ante la duda no se acusa: para un alumno, quedar marcado por algo que no se
  // pudo medir es peor que no detectar una inyeccion, que igual no es veredicto
  // (L2.5: la decision es humana y hay re-inferencia server-side).
  if (signals.medicionValida === false) return false;
  const feedLoopLike = signals.interFramePixelVariance < 1e-6;
  const tooStable = signals.faceCountStability >= 0.999;
  return feedLoopLike && tooStable;
}

/**
 * Resultado pasivo de la CAPTURA ENTERA, no del instante en que termino.
 *
 * El pasivo busca EVIDENCIA DE VIDA: parpadeo, micro-movimientos y profundidad.
 * Es una pregunta acumulativa ("¿en algun momento se comporto como una persona?"),
 * no instantanea. Evaluarla frame a frame y quedarse con el ultimo la convertia en
 * "¿se estaba moviendo justo al terminar?", que es otra pregunta y con una respuesta
 * previsible: no, porque el alumno ya completo los retos y esta esperando quieto.
 *
 * Por eso el registro mostraba los tres retos completados y el pasivo no superado
 * al mismo tiempo, dos cosas que no pueden ser ciertas juntas: una foto no parpadea
 * a pedido ni sonrie ni gira la cabeza.
 *
 * No debilita la defensa contra fotos: una imagen plana no produce vida en NINGUN
 * frame, asi que `algunaVezOk` nunca se enciende.
 */
export function resumirPasivoDeLaCaptura(captura: {
  /** Si hubo al menos un frame con las tres senales pasivas positivas. */
  algunaVezOk: boolean;
  /** Cuantos frames se alcanzaron a evaluar (0 = no se midio nada). */
  framesEvaluados: number;
}): boolean {
  if (captura.framesEvaluados <= 0) return false;
  return captura.algunaVezOk;
}

/**
 * Veredicto de vida de la captura, combinando las DOS fuentes de evidencia.
 *
 * ## Por que los retos activos alcanzan solos
 *
 * Completar los retos es evidencia DIRECTA y mas fuerte que cualquier heuristica
 * de varianza: una foto no parpadea, no sonrie y no gira la cabeza cuando se le
 * pide. Un video grabado tampoco alcanza, porque los retos se piden en ORDEN
 * ALEATORIO (`fisherYatesShuffle`) y habria que haber adivinado la secuencia.
 *
 * Antes el veredicto miraba SOLO el pasivo, cuyos umbrales estan sin calibrar
 * contra camaras reales y no se cumplen ni con una persona de carne y hueso. El
 * resultado era absurdo y quedaba escrito en el legajo del alumno: "Liveness
 * pasivo: No superado" al lado de los tres retos completados. Dos afirmaciones
 * que no pueden ser ciertas a la vez.
 *
 * ## Que NO se debilita
 *
 * Sin retos completos y sin pasivo, sigue sin haber evidencia de vida. Y esto no
 * es el veredicto final del sistema: el backend re-infiere y la decision es
 * humana (L2.5, regla dura #5 y #6).
 */
export function hayEvidenciaDeVida(captura: {
  /** Resultado de las senales pasivas sobre toda la captura. */
  pasivoOk: boolean;
  /** Retos que se le pidieron al alumno. */
  pedidos: readonly string[];
  /** Retos que efectivamente resolvio. */
  resueltos: readonly string[];
}): boolean {
  if (captura.pasivoOk) return true;
  // Sin retos pedidos no hay nada que demostrar: "resolvio los 0 que le pedi" no
  // es evidencia de nada, asi que ahi decide el pasivo.
  if (captura.pedidos.length === 0) return false;
  const hechos = new Set(captura.resueltos);
  return captura.pedidos.every((r) => hechos.has(r));
}

/** Como se llama cada reto en pantalla. El id interno nunca se le muestra a nadie. */
const NOMBRE_DE_RETO: Record<string, string> = {
  parpadear: 'Parpadear',
  girar_cabeza: 'Girar la cabeza',
  sonreír: 'Sonreír',
  sonreir: 'Sonreír',
};

/**
 * Nombre legible de un reto.
 *
 * El registro de sesion mostraba el identificador crudo — "girar_cabeza", con
 * guion bajo — que es como se llama adentro del codigo, no como se le habla a una
 * persona. Un id desconocido (un reto nuevo del backend) tampoco se filtra crudo:
 * se le saca el guion bajo y se le pone mayuscula.
 */
export function nombreDelReto(id: string): string {
  const conocido = NOMBRE_DE_RETO[id];
  if (conocido) return conocido;
  const legible = id.replace(/_/g, ' ').trim();
  return legible.charAt(0).toUpperCase() + legible.slice(1);
}

/** Conteo de rostros agregado del clip: util para reportar multiples rostros. */
export function aggregateFaceCount(frames: FrameResult[]): number {
  if (frames.length === 0) return 0;
  return Math.max(...frames.map((f) => f.face_count));
}

// ---------------------------------------------------------------------------
// C-67 Grupo 5 — Propagación de señales PAD al backend (Task 5.4)
// ---------------------------------------------------------------------------

/**
 * Payload de biometría de proctoring que se envía al backend tras la captura.
 *
 * Contiene las tres señales PAD reales (sin hardcodes):
 *   - liveness_ok:          señal pasiva real (parpadeo + micro-movimientos + profundidad 3D).
 *   - retos_resueltos:      retos activos completados realmente por el alumno.
 *   - resultado:            señal de cámara virtual detectada vs. verificado.
 *   - embedding (opcional): descriptor 128-d del rostro vivo para re-inferencia server-side.
 *
 * Este payload SE REPORTA al backend como evidencia (C-46, D6). El backend lo
 * firma y re-infiere (RN-GLB-01). El cliente NO emite veredicto (L2.5, regla dura #5).
 *
 * Invariante (Task 5.4): NUNCA hardcodear liveness_ok=true ni retos_resueltos=['...'];
 * los valores SIEMPRE vienen de los parámetros reales de onComplete del BiometricCapture.
 */
export interface BiometriaProctoringPayload {
  liveness_ok: boolean;
  retos_resueltos: string[];
  embedding?: number[];
  resultado: "verificado" | "camara_virtual_detectada";
}

/**
 * Construye el payload de biometría de proctoring a partir de las señales PAD reales.
 *
 * Función PURA (sin efectos secundarios) para que sea testeable (Task 5.4).
 * Esta función es la fuente de verdad del mapping de señales PAD al payload del backend.
 * Biometria.tsx la usa en lugar de construir el payload inline (evita hardcodes accidentales).
 *
 * @param passiveOk            - Señal pasiva real de `passivePassed(derivePassiveSignals(...))`.
 * @param retosResueltos       - Array real de retos completados desde BiometricCapture.onComplete.
 * @param virtualCameraDetected - Señal real de `detectVirtualCamera(...)`.
 * @param embedding            - Descriptor 128-d del rostro vivo (dato sensible, Ley 25.326).
 *                               Nunca se loguea ni se muestra en UI.
 */
export function buildBiometriaProctoringPayload(
  passiveOk: boolean,
  retosResueltos: string[],
  virtualCameraDetected: boolean,
  embedding?: number[],
): BiometriaProctoringPayload {
  return {
    liveness_ok: passiveOk,
    retos_resueltos: retosResueltos,
    ...(embedding !== undefined ? { embedding } : {}),
    resultado: virtualCameraDetected ? "camara_virtual_detectada" : "verificado",
  };
}
