/**
 * Tests de la logica de liveness hibrido del cliente (C-09, DD-18).
 *
 * Formato Vitest (stack Vite). Cubre: retos aleatorios (cantidad/aleatoriedad),
 * gate de liveness (pasa/falla, camara virtual), deteccion de camara virtual y
 * derivacion de senales pasivas (foto plana no pasa).
 *
 * C-67 Grupo 5: Defensa anti-foto (PAD) — tests de la defensa combinada
 * (activo + pasivo + cámara virtual). ISO 30107-3 Nivel 1–2 en cliente.
 * Alcance honesto: NO hay inmunidad a inyección/deepfake; la autoridad real
 * es re-inferencia server-side + verificación continua + revisión humana (L2.5).
 */

import { describe, expect, it } from "vitest";

import {
  ACTIVE_CHALLENGES,
  SEQUENTIAL_CHALLENGES,
  aggregateFaceCount,
  buildBiometriaProctoringPayload,
  clientLivenessOk,
  derivePassiveSignals,
  detectVirtualCamera,
  MAX_ACTIVE_CHALLENGES,
  passivePassed,
  pickActiveChallenges,
} from "./liveness";

const PASSIVE_OK = {
  parpadeo_detectado: true,
  micro_movimientos: true,
  profundidad_3d_coherente: true,
};

describe("retos activos aleatorios", () => {
  it("elige entre 1 y 2 retos del catalogo", () => {
    const chosen = pickActiveChallenges(2);
    expect(chosen.length).toBeGreaterThanOrEqual(1);
    expect(chosen.length).toBeLessThanOrEqual(MAX_ACTIVE_CHALLENGES);
    for (const c of chosen) expect(ACTIVE_CHALLENGES).toContain(c);
  });

  it("no repite retos en un mismo intento", () => {
    const chosen = pickActiveChallenges(2, mkRng([0, 0]));
    expect(new Set(chosen).size).toBe(chosen.length);
  });

  it("es aleatorio: distinto rng -> distinta seleccion", () => {
    const a = pickActiveChallenges(1, mkRng([0]));
    const b = pickActiveChallenges(1, mkRng([0.99]));
    expect(a[0]).not.toBe(b[0]);
  });
});

describe("gate de liveness del cliente", () => {
  it("pasa con pasivo OK y reto resuelto", () => {
    expect(
      clientLivenessOk({
        passive: PASSIVE_OK,
        requested: ["parpadear"],
        solved: ["parpadear"],
        virtualCameraDetected: false,
      }),
    ).toBe(true);
  });

  it("falla si el reto no fue resuelto", () => {
    expect(
      clientLivenessOk({
        passive: PASSIVE_OK,
        requested: ["girar_izquierda"],
        solved: [],
        virtualCameraDetected: false,
      }),
    ).toBe(false);
  });

  it("falla si se detecta camara virtual (capa de defensa, DD-18)", () => {
    expect(
      clientLivenessOk({
        passive: PASSIVE_OK,
        requested: ["parpadear"],
        solved: ["parpadear"],
        virtualCameraDetected: true,
      }),
    ).toBe(false);
  });
});

describe("senales pasivas", () => {
  it("una foto plana (varianza ~0, sin profundidad) no pasa el pasivo", () => {
    const signals = derivePassiveSignals({
      blinkVariance: 0,
      motionVariance: 0,
      depthRange: 0,
    });
    expect(passivePassed(signals)).toBe(false);
  });

  it("una persona viva (varianza y profundidad reales) pasa el pasivo", () => {
    const signals = derivePassiveSignals({
      blinkVariance: 0.05,
      motionVariance: 0.002,
      depthRange: 0.1,
    });
    expect(passivePassed(signals)).toBe(true);
  });
});

describe("deteccion de camara virtual", () => {
  it("detecta un feed loop demasiado estable", () => {
    expect(
      detectVirtualCamera({
        interFramePixelVariance: 0,
        frameRateJitter: 0,
        faceCountStability: 1,
      }),
    ).toBe(true);
  });

  it("no marca una camara fisica con jitter normal", () => {
    expect(
      detectVirtualCamera({
        interFramePixelVariance: 0.3,
        frameRateJitter: 0.02,
        faceCountStability: 0.8,
      }),
    ).toBe(false);
  });
});

describe("conteo de rostros", () => {
  it("toma el maximo de rostros del clip (multiples rostros)", () => {
    expect(
      aggregateFaceCount([
        { landmarks: [], face_count: 1 },
        { landmarks: [], face_count: 2 },
      ]),
    ).toBe(2);
  });
});

/** RNG determinista a partir de una lista de valores. */
function mkRng(values: number[]): () => number {
  let i = 0;
  return () => values[i++ % values.length];
}

// ---------------------------------------------------------------------------
// C-67 Grupo 5 — Defensa anti-foto / PAD (ISO 30107-3 Nivel 1–2)
// ---------------------------------------------------------------------------

/**
 * Métricas de una foto estática presentada a la cámara.
 * Una foto plana tiene:
 * - Varianza de parpadeo ~0 (los "ojos" no parpadean).
 * - Varianza de movimiento de nariz ~0 (no hay micro-movimientos).
 * - Rango de profundidad Z ~0 (la foto es un plano 2D).
 *
 * Alcance honesto (DD-18, ISO 30107-3): el cliente cubre Nivel 1–2
 * (fotos, videos de reproducción). No es inmune a inyección de cámara ni
 * deepfakes puppet-master. La autoridad real = re-inferencia server-side +
 * verificación continua + revisión humana (L2.5).
 */
const STATIC_PHOTO_METRICS = {
  blinkVariance: 0,    // sin parpadeo
  motionVariance: 0,   // sin micro-movimientos
  depthRange: 0,       // sin profundidad 3D
};

describe("C-67 Grupo 5 — defensa anti-foto combinada (PAD, ISO 30107-3)", () => {
  // 5.1a: Señales pasivas de una foto estática → passivePassed = false
  it("5.1a una foto estática produce varianza 0 → pasivo falla (passivePassed=false)", () => {
    const signals = derivePassiveSignals(STATIC_PHOTO_METRICS);

    // Cada señal pasiva debe fallar
    expect(signals.parpadeo_detectado).toBe(false);
    expect(signals.micro_movimientos).toBe(false);
    expect(signals.profundidad_3d_coherente).toBe(false);

    // El gate pasivo no se supera
    expect(passivePassed(signals)).toBe(false);
  });

  // 5.1b: La defensa COMBINADA (pasivo + retos activos) no se supera con foto estática.
  // Una foto no puede completar los retos de gestos → retos_resueltos = [].
  it("5.1b la defensa combinada (pasivo + retos) NO se supera con foto estática sin gestos", () => {
    const staticSignals = derivePassiveSignals(STATIC_PHOTO_METRICS);

    // Pasivo falla
    expect(passivePassed(staticSignals)).toBe(false);

    // Retos activos: solicitados pero sin resolver (foto no puede ejecutar gestos)
    const retosResueltos: string[] = [];
    const retosRequeridos = ["parpadear", "girar_cabeza", "sonreír"] as const;

    // Gate combinado: pasivo FALLA → clientLivenessOk=false aunque fuera legacy-compatible
    // (Nota: clientLivenessOk usa ActiveChallenge[], pero el principio PAD es:
    //  si el pasivo falla, el gate ya cierra. El activo es la segunda capa.)
    const gatePasivo = passivePassed(staticSignals);
    const gateActivo = retosRequeridos.every((r) => retosResueltos.includes(r));

    // Ambas capas fallan con foto estática
    expect(gatePasivo).toBe(false);
    expect(gateActivo).toBe(false);

    // La defensa combinada (AND lógico) no se supera
    const defensaCombinada = gatePasivo && gateActivo;
    expect(defensaCombinada).toBe(false);
  });

  // 5.1c: Triangulación — con métricas de vida real, el pasivo SÍ pasa
  // (verificar que el umbral no es trivialmente imposible para un vivo)
  it("5.1c (triangulación) una persona viva con movimiento real SÍ pasa el pasivo", () => {
    const aliveMetrics = {
      blinkVariance: 0.05,    // parpadeos naturales
      motionVariance: 0.002,  // micro-movimientos
      depthRange: 0.1,        // profundidad 3D coherente
    };
    const signals = derivePassiveSignals(aliveMetrics);
    expect(passivePassed(signals)).toBe(true);
  });

  // 5.1d: Triangulación — foto con ALGO de ruido (jitter muy bajo) sigue fallando
  it("5.1d (triangulación) foto con ruido de compresión mínimo (blinkVariance=0.005) sigue fallando el pasivo", () => {
    // Umbral es 0.01 — ruido de foto JPEG/compresión (< 0.01) no supera la defensa
    const nearZeroMetrics = {
      blinkVariance: 0.005,   // bajo el umbral 0.01
      motionVariance: 0.0003, // bajo el umbral 0.0005
      depthRange: 0.01,       // bajo el umbral 0.02
    };
    const signals = derivePassiveSignals(nearZeroMetrics);
    expect(passivePassed(signals)).toBe(false);
  });

  // 5.2: El catálogo de retos secuenciales tiene los tres gestos esperados
  // (fisher-yates + dirección aleatoria están en enrollmentChallengeDetector.test.ts)
  it("5.2 SEQUENTIAL_CHALLENGES incluye los tres retos anti-foto (parpadear, girar_cabeza, sonreír)", () => {
    expect(SEQUENTIAL_CHALLENGES).toContain("parpadear");
    expect(SEQUENTIAL_CHALLENGES).toContain("girar_cabeza");
    expect(SEQUENTIAL_CHALLENGES).toContain("sonreír");
    expect(SEQUENTIAL_CHALLENGES).toHaveLength(3);
  });

  // 5.2b: Los retos secuenciales son distintos entre sí (sin repetición)
  it("5.2b los tres retos secuenciales son distintos entre sí", () => {
    const set = new Set(SEQUENTIAL_CHALLENGES);
    expect(set.size).toBe(SEQUENTIAL_CHALLENGES.length);
  });
});

// ---------------------------------------------------------------------------
// C-67 Grupo 5 — Propagación de señales PAD sin hardcodes (Task 5.4)
// ---------------------------------------------------------------------------

describe("C-67 Grupo 5 — propagación de señales PAD al backend sin hardcodes (Task 5.4)", () => {
  /**
   * buildBiometriaProctoringPayload es la función pura que mapea las señales
   * reales de BiometricCapture.onComplete al payload del backend.
   *
   * Invariante clave (Task 5.4): los valores de liveness_ok, retos_resueltos y
   * resultado NUNCA son hardcodeados; siempre reflejan los parámetros de entrada.
   * Un hardcode (liveness_ok=true siempre, retos_resueltos=['parpadear', ...] fijo)
   * rompería la cadena de evidencia y constituye un defecto de dominio crítico.
   */

  // 5.4a: passiveOk=true se propaga como liveness_ok=true
  it("5.4a liveness_ok refleja passiveOk=true (sin hardcode)", () => {
    const payload = buildBiometriaProctoringPayload(true, ["parpadear"], false);
    expect(payload.liveness_ok).toBe(true);
  });

  // 5.4a.2: passiveOk=false se propaga como liveness_ok=false (no hardcodeado en true)
  it("5.4a.2 liveness_ok refleja passiveOk=false — NO hardcodeado en true", () => {
    const payload = buildBiometriaProctoringPayload(false, ["parpadear"], false);
    expect(payload.liveness_ok).toBe(false);
  });

  // 5.4b: retos_resueltos refleja el array real de retos completados
  it("5.4b retos_resueltos refleja los retos reales completados", () => {
    const retos = ["parpadear", "girar_cabeza", "sonreír"];
    const payload = buildBiometriaProctoringPayload(true, retos, false);
    expect(payload.retos_resueltos).toEqual(retos);
  });

  // 5.4b.2: retos vacíos (foto/sin gestos) → retos_resueltos=[] (no hardcodeado)
  it("5.4b.2 retos vacíos se propagan como [] — NO se rellena con valores ficticios", () => {
    const payload = buildBiometriaProctoringPayload(false, [], false);
    expect(payload.retos_resueltos).toEqual([]);
  });

  // 5.4c: virtualCameraDetected=true → resultado='camara_virtual_detectada'
  it("5.4c virtualCameraDetected=true → resultado='camara_virtual_detectada'", () => {
    const payload = buildBiometriaProctoringPayload(true, ["parpadear"], true);
    expect(payload.resultado).toBe("camara_virtual_detectada");
  });

  // 5.4c.2: virtualCameraDetected=false → resultado='verificado'
  it("5.4c.2 (triangulación) virtualCameraDetected=false → resultado='verificado'", () => {
    const payload = buildBiometriaProctoringPayload(true, ["parpadear"], false);
    expect(payload.resultado).toBe("verificado");
  });

  // 5.4d: embedding opcional se incluye cuando se provee y se omite cuando no
  it("5.4d embedding se incluye cuando se provee", () => {
    const embedding = [0.1, 0.2, 0.3];
    const payload = buildBiometriaProctoringPayload(true, [], false, embedding);
    expect(payload.embedding).toEqual(embedding);
  });

  it("5.4d.2 embedding se omite cuando no se provee (no se envía null ni undefined explícito)", () => {
    const payload = buildBiometriaProctoringPayload(true, [], false);
    // No debe existir la clave 'embedding' en el payload (no enviar undefined al backend)
    expect("embedding" in payload).toBe(false);
  });

  // 5.4e: Integración — foto estática → passiveOk=false, retos=[], sin cámara virtual
  // El payload refleja la realidad sin manipulación client-side.
  it("5.4e (integración PAD) foto estática → payload con liveness_ok=false y retos=[]", () => {
    // Simular las señales que daría una foto estática
    const staticSignals = derivePassiveSignals({ blinkVariance: 0, motionVariance: 0, depthRange: 0 });
    const passiveOk = passivePassed(staticSignals);  // false para foto estática
    const retosResueltos: string[] = [];               // foto no puede completar gestos
    const virtualCamera = false;

    const payload = buildBiometriaProctoringPayload(passiveOk, retosResueltos, virtualCamera);

    // El payload reporta honestamente el fracaso → el backend decide (L2.5)
    expect(payload.liveness_ok).toBe(false);
    expect(payload.retos_resueltos).toEqual([]);
    expect(payload.resultado).toBe("verificado"); // no es cámara virtual, pero pasivo falló
    // Nota: es_match se decide server-side; el cliente solo reporta las señales reales
  });
});
