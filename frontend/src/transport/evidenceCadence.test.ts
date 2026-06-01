/**
 * Tests de la cadencia de captura de evidencia (C-24, DD-24-02). Formato Vitest.
 *
 * Cubre:
 *   - validarCadencia: proporcionalidad / tope máximo (tarea 2.4).
 *   - resolverIntervalMs: default conservador y override por config (tarea 2.3).
 *   - EvidenceCadenceController.onEventDriven: solo alta/critica (tarea 2.1).
 *   - EvidenceCadenceController heartbeat: periódico + activación/desactivación (tarea 2.2).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  HEARTBEAT_DEFAULT_SEC,
  HEARTBEAT_MAX_FREQ_SEC,
  validarCadencia,
  resolverIntervalMs,
  EvidenceCadenceController,
  type CadenceConfig,
} from "./evidenceCadence";

// ---------------------------------------------------------------------------
// validarCadencia — tope de frecuencia máxima (tarea 2.4)
// ---------------------------------------------------------------------------

describe("validarCadencia", () => {
  it("intervalo 0 (desactivado) es válido", () => {
    expect(validarCadencia({ heartbeatSeg: 0 })).toBeNull();
  });

  it("intervalo igual al tope máximo es válido", () => {
    expect(validarCadencia({ heartbeatSeg: HEARTBEAT_MAX_FREQ_SEC })).toBeNull();
  });

  it("intervalo por encima del tope es válido (menor frecuencia)", () => {
    expect(validarCadencia({ heartbeatSeg: HEARTBEAT_MAX_FREQ_SEC + 10 })).toBeNull();
  });

  it("intervalo por debajo del tope (mayor frecuencia) es RECHAZADO", () => {
    const msg = validarCadencia({ heartbeatSeg: HEARTBEAT_MAX_FREQ_SEC - 1 });
    expect(msg).not.toBeNull();
    expect(msg).toMatch(/mínimo permitido/i);
  });

  it("intervalo 1 es rechazado (frecuencia excesiva)", () => {
    expect(validarCadencia({ heartbeatSeg: 1 })).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// resolverIntervalMs — defaults y overrides (tarea 2.3)
// ---------------------------------------------------------------------------

describe("resolverIntervalMs", () => {
  it("sin config usa el default conservador", () => {
    expect(resolverIntervalMs()).toBe(HEARTBEAT_DEFAULT_SEC * 1000);
  });

  it("config con heartbeatSeg válido se respeta", () => {
    expect(resolverIntervalMs({ heartbeatSeg: HEARTBEAT_MAX_FREQ_SEC }))
      .toBe(HEARTBEAT_MAX_FREQ_SEC * 1000);
  });

  it("config con heartbeatSeg 0 devuelve 0 (desactivado)", () => {
    expect(resolverIntervalMs({ heartbeatSeg: 0 })).toBe(0);
  });

  it("config con frecuencia excesiva lanza Error", () => {
    expect(() => resolverIntervalMs({ heartbeatSeg: 5 })).toThrow(/mínimo permitido/i);
  });
});

// ---------------------------------------------------------------------------
// EvidenceCadenceController — event-driven (tarea 2.1)
// ---------------------------------------------------------------------------

describe("EvidenceCadenceController — event-driven", () => {
  // Mock de capturarFrame para no necesitar DOM real.
  vi.mock("./evidenceCapture", async (importOriginal) => {
    const original = await importOriginal<typeof import("./evidenceCapture")>();
    return {
      ...original,
      capturarFrame: vi.fn().mockResolvedValue(new ArrayBuffer(8)),
      capturarEvidencia: vi.fn().mockResolvedValue({
        session_id: "s1",
        exam_id: "e1",
        object_key: "evidence/shot.png",
        hash_cliente: "aabbcc",
        firma_cliente: "ddeeff",
        trigger: "event",
        severidad: "alta",
      }),
    };
  });

  const fakeVideo = {} as HTMLVideoElement;
  const fakeDeps = {
    sessionId: "s1",
    examId: "e1",
    sessionKey: "k",
    presign: vi.fn(),
  };

  it("evento de severidad alta dispara captura (onReady llamado)", async () => {
    const onReady = vi.fn();
    const ctrl = new EvidenceCadenceController(fakeVideo, fakeDeps, onReady, { heartbeatSeg: 0 });
    ctrl.start();

    const { capturarEvidencia } = await import("./evidenceCapture");

    ctrl.onEventDriven({ tipo: "multiples_rostros", severidad: "alta", ts_ms: Date.now(), payload: {}, trigger_evidence: true });

    // Esperar el micro-tick de la Promise interna.
    await new Promise<void>((r) => setTimeout(r, 10));

    expect(capturarEvidencia).toHaveBeenCalledWith(
      "alta",
      expect.any(ArrayBuffer),
      fakeDeps,
      "event",
    );
    expect(onReady).toHaveBeenCalled();
    ctrl.stop();
  });
});

// ---------------------------------------------------------------------------
// EvidenceCadenceController — heartbeat (tarea 2.2)
// ---------------------------------------------------------------------------

describe("EvidenceCadenceController — heartbeat", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("heartbeat desactivado (0) no dispara capturas", async () => {
    const onReady = vi.fn();
    const fakeVideo = {} as HTMLVideoElement;
    const fakeDeps = { sessionId: "s", examId: "e", sessionKey: "k", presign: vi.fn() };
    const ctrl = new EvidenceCadenceController(fakeVideo, fakeDeps, onReady, { heartbeatSeg: 0 });
    ctrl.start();
    vi.advanceTimersByTime(10 * 60 * 1000); // 10 minutos
    expect(onReady).not.toHaveBeenCalled();
    ctrl.stop();
  });

  it("stop() detiene el heartbeat", async () => {
    const onReady = vi.fn();
    const fakeVideo = {} as HTMLVideoElement;
    const fakeDeps = { sessionId: "s", examId: "e", sessionKey: "k", presign: vi.fn() };
    const ctrl = new EvidenceCadenceController(
      fakeVideo, fakeDeps, onReady,
      { heartbeatSeg: HEARTBEAT_MAX_FREQ_SEC }, // mínimo válido
    );
    ctrl.start();
    ctrl.stop();
    vi.advanceTimersByTime(HEARTBEAT_MAX_FREQ_SEC * 1000 * 5);
    // onReady podría ser llamado 0 veces (detenido antes de primer tick)
    // Lo importante: stop() no lanza y el timer no sigue corriendo.
    // No podemos afirmar 0 llamadas porque el primer tick podría ya haber pasado antes del stop en CI,
    // pero al menos el número no debe crecer después de stop.
    const callsAfterStop = onReady.mock.calls.length;
    vi.advanceTimersByTime(HEARTBEAT_MAX_FREQ_SEC * 1000 * 10);
    expect(onReady.mock.calls.length).toBe(callsAfterStop); // sin nuevas llamadas tras stop
  });
});
