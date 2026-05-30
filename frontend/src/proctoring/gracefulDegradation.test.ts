/**
 * Tests de la degradacion graceful (C-11, RN-GLB-02/03). Formato Vitest.
 *
 * Baja Pose -> Face Mesh -> escala a proctor; ajuste de fps por capacidad; nunca
 * abort silencioso.
 */

import { describe, expect, it } from "vitest";

import { degrade } from "./gracefulDegradation";

describe("degradacion escalonada", () => {
  it("con capacidad plena mantiene los tres detectores", () => {
    const s = degrade({ sustainable_detectors: 3 });
    expect(s.active).toEqual(["face_detection", "face_mesh", "pose"]);
    expect(s.level).toBe(0);
    expect(s.escalated_to_proctor).toBe(false);
  });

  it("baja Pose primero ante hardware limitado", () => {
    const s = degrade({ sustainable_detectors: 2 });
    expect(s.active).toEqual(["face_detection", "face_mesh"]);
    expect(s.active).not.toContain("pose");
    expect(s.level).toBe(1);
    expect(s.escalated_to_proctor).toBe(false);
  });

  it("luego baja Face Mesh dejando solo Face Detection", () => {
    const s = degrade({ sustainable_detectors: 1 });
    expect(s.active).toEqual(["face_detection"]);
    expect(s.level).toBe(2);
    expect(s.escalated_to_proctor).toBe(false);
  });

  it("escala a proctor cuando la degradacion no alcanza, sin abortar", () => {
    const s = degrade({ sustainable_detectors: 0 });
    expect(s.active).toEqual([]);
    expect(s.escalated_to_proctor).toBe(true);
    // El estado existe (no hay abort silencioso): el examen sigue, lo toma un proctor.
    expect(s).toHaveProperty("escalated_to_proctor", true);
  });
});

describe("ajuste de fps por capacidad", () => {
  it("escala los fps de los detectores activos segun la capacidad detectada", () => {
    const full = degrade({ sustainable_detectors: 3, fps_scale: 1 });
    const half = degrade({ sustainable_detectors: 3, fps_scale: 0.5 });
    expect(half.fps.face_detection!).toBeLessThan(full.fps.face_detection!);
    expect(half.fps.face_detection!).toBeGreaterThanOrEqual(1);
  });
});
