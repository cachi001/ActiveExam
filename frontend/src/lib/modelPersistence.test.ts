/**
 * Tests de modelPersistence (C-67 fix): el predicado que decide qué assets de
 * modelos de IA deben cachearse de forma persistente (Service Worker cache-first).
 *
 * Solo deben cachearse los modelos pesados de visión:
 *  - /mediapipe/**  (WASM ~11 MB + .task de MediaPipe)
 *  - /models/**     (modelos de face-api: descriptor 128-d, landmarks 68, detector)
 *
 * NADA más debe entrar al cache del SW (código de la app, API, HMR) para no servir
 * nunca una versión vieja por error.
 */

import { describe, expect, it } from "vitest";
import { isModelAssetPath } from "./modelPersistence";

describe("isModelAssetPath — qué se persiste en el cache de modelos", () => {
  it("cachea los assets de MediaPipe (wasm y .task)", () => {
    expect(isModelAssetPath("/mediapipe/wasm/vision_wasm_internal.wasm")).toBe(true);
    expect(isModelAssetPath("/mediapipe/face_landmarker.task")).toBe(true);
    expect(isModelAssetPath("/mediapipe/face_detector_short_range.task")).toBe(true);
  });

  it("cachea los modelos de face-api en /models", () => {
    expect(isModelAssetPath("/models/face_recognition_model.bin")).toBe(true);
    expect(isModelAssetPath("/models/tiny_face_detector_model-weights_manifest.json")).toBe(true);
  });

  it("NO cachea código de la app, API ni otros estáticos", () => {
    expect(isModelAssetPath("/")).toBe(false);
    expect(isModelAssetPath("/index.html")).toBe(false);
    expect(isModelAssetPath("/src/main.tsx")).toBe(false);
    expect(isModelAssetPath("/assets/index-abc123.js")).toBe(false);
    expect(isModelAssetPath("/api/v1/auth/me")).toBe(false);
    expect(isModelAssetPath("/silent-check-sso.html")).toBe(false);
  });

  it("acepta una URL absoluta y evalúa solo su pathname", () => {
    expect(isModelAssetPath("https://ejemplo.trycloudflare.com/mediapipe/face_landmarker.task")).toBe(true);
    expect(isModelAssetPath("https://ejemplo.trycloudflare.com/api/v1/proctoring/health")).toBe(false);
  });

  it("no se deja engañar por la subcadena en otra posición (evita falsos positivos)", () => {
    // '/models' debe ser un segmento de ruta, no aparecer en el medio de otro path.
    expect(isModelAssetPath("/api/models-list")).toBe(false);
    expect(isModelAssetPath("/algo/mediapipe/x.task")).toBe(false);
  });
});
