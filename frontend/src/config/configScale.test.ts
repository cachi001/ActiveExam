/**
 * Tests de configScale — conversión bidireccional interno ↔ amigable.
 * Patrón: lógica PURA, sin DOM, sin red.
 * TDD: RED → GREEN → TRIANGULATE → REFACTOR.
 */

import { describe, it, expect } from 'vitest';
import {
  msToSeg,
  segToMs,
  gazeDeviationToLabel,
  labelToGazeDeviation,
  gazeFixationToLabel,
  labelToGazeFixation,
  toFriendly,
  toInternal,
  framesToDisplay,
} from './configScale';
import type { SensibilidadLabel, ConfigInternal } from './configScale';

// ---------------------------------------------------------------------------
// msToSeg / segToMs
// ---------------------------------------------------------------------------

describe('msToSeg', () => {
  it('convierte 3000ms a 3 segundos', () => {
    expect(msToSeg(3000)).toBe(3);
  });

  it('convierte 2500ms a 2.5 segundos', () => {
    expect(msToSeg(2500)).toBe(2.5);
  });

  it('convierte 0ms a 0 segundos', () => {
    expect(msToSeg(0)).toBe(0);
  });
});

describe('segToMs', () => {
  it('convierte 3 segundos a 3000ms', () => {
    expect(segToMs(3)).toBe(3000);
  });

  it('convierte 2.5 segundos a 2500ms', () => {
    expect(segToMs(2.5)).toBe(2500);
  });

  it('redondea correctamente (evita flotantes)', () => {
    // 1.001 * 1000 = 1001.0 (exacto en este caso)
    expect(segToMs(1.001)).toBe(1001);
  });
});

describe('round-trip ms ↔ seg', () => {
  it('3000ms → 3s → 3000ms (round-trip preserva el valor interno)', () => {
    expect(segToMs(msToSeg(3000))).toBe(3000);
  });

  it('2500ms → 2.5s → 2500ms', () => {
    expect(segToMs(msToSeg(2500))).toBe(2500);
  });

  it('0ms → 0s → 0ms', () => {
    expect(segToMs(msToSeg(0))).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// gazeDeviationToLabel
// ---------------------------------------------------------------------------

describe('gazeDeviationToLabel', () => {
  it('0.40 (tolerante) → "baja"', () => {
    expect(gazeDeviationToLabel(0.40)).toBe<SensibilidadLabel>('baja');
  });

  it('0.25 (medio) → "media"', () => {
    expect(gazeDeviationToLabel(0.25)).toBe<SensibilidadLabel>('media');
  });

  it('0.15 (sensible) → "alta"', () => {
    expect(gazeDeviationToLabel(0.15)).toBe<SensibilidadLabel>('alta');
  });

  // Bordes exactos
  it('0.35 (límite baja) → "baja"', () => {
    expect(gazeDeviationToLabel(0.35)).toBe<SensibilidadLabel>('baja');
  });

  it('0.20 (límite media) → "media"', () => {
    expect(gazeDeviationToLabel(0.20)).toBe<SensibilidadLabel>('media');
  });

  it('0.19 (justo debajo de media) → "alta"', () => {
    expect(gazeDeviationToLabel(0.19)).toBe<SensibilidadLabel>('alta');
  });
});

// ---------------------------------------------------------------------------
// labelToGazeDeviation (round-trip sobre la etiqueta)
// ---------------------------------------------------------------------------

describe('labelToGazeDeviation → gazeDeviationToLabel (round-trip label)', () => {
  const labels: SensibilidadLabel[] = ['baja', 'media', 'alta'];

  for (const label of labels) {
    it(`round-trip preserva "${label}"`, () => {
      const internal = labelToGazeDeviation(label);
      expect(gazeDeviationToLabel(internal)).toBe(label);
    });
  }
});

// ---------------------------------------------------------------------------
// gazeFixationToLabel
// ---------------------------------------------------------------------------

describe('gazeFixationToLabel', () => {
  it('0.35 (tolerante) → "baja"', () => {
    expect(gazeFixationToLabel(0.35)).toBe<SensibilidadLabel>('baja');
  });

  it('0.22 (medio) → "media"', () => {
    expect(gazeFixationToLabel(0.22)).toBe<SensibilidadLabel>('media');
  });

  it('0.10 (exigente) → "alta"', () => {
    expect(gazeFixationToLabel(0.10)).toBe<SensibilidadLabel>('alta');
  });

  it('límite 0.30 → "baja"', () => {
    expect(gazeFixationToLabel(0.30)).toBe<SensibilidadLabel>('baja');
  });

  it('0.15 (límite media/alta) → "media"', () => {
    expect(gazeFixationToLabel(0.15)).toBe<SensibilidadLabel>('media');
  });

  it('0.14 (debajo del límite) → "alta"', () => {
    expect(gazeFixationToLabel(0.14)).toBe<SensibilidadLabel>('alta');
  });
});

describe('labelToGazeFixation → gazeFixationToLabel (round-trip label)', () => {
  const labels: SensibilidadLabel[] = ['baja', 'media', 'alta'];

  for (const label of labels) {
    it(`round-trip preserva "${label}"`, () => {
      const internal = labelToGazeFixation(label);
      expect(gazeFixationToLabel(internal)).toBe(label);
    });
  }
});

// ---------------------------------------------------------------------------
// framesToDisplay
// ---------------------------------------------------------------------------

describe('framesToDisplay', () => {
  it('5 frames → display 5 (sin conversión)', () => {
    expect(framesToDisplay(5)).toBe(5);
  });

  it('1 frame → display 1', () => {
    expect(framesToDisplay(1)).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// toFriendly / toInternal (round-trip completo)
// ---------------------------------------------------------------------------

const SAMPLE_CONFIG: ConfigInternal = {
  face_absent_ms: 3000,
  multiple_faces_frames: 5,
  gaze_deviation_threshold: 0.20,
  gaze_sustained_ms: 2500,
  gaze_fixation_tolerance: 0.25,
  umbral_cola_revision: 70,
  retencion_dias_default: 30,
};

describe('toFriendly', () => {
  it('convierte face_absent_ms a segundos', () => {
    const f = toFriendly(SAMPLE_CONFIG);
    expect(f.face_absent_seg).toBe(3);
  });

  it('convierte gaze_sustained_ms a segundos', () => {
    const f = toFriendly(SAMPLE_CONFIG);
    expect(f.gaze_sustained_seg).toBe(2.5);
  });

  it('convierte gaze_deviation_threshold 0.20 a "media"', () => {
    const f = toFriendly(SAMPLE_CONFIG);
    expect(f.gaze_deviation_label).toBe('media');
  });

  it('convierte gaze_fixation_tolerance 0.25 a "media"', () => {
    const f = toFriendly(SAMPLE_CONFIG);
    expect(f.gaze_fixation_label).toBe('media');
  });

  it('pasa umbral_cola_revision sin cambio', () => {
    const f = toFriendly(SAMPLE_CONFIG);
    expect(f.umbral_cola_revision).toBe(70);
  });

  it('pasa retencion_dias_default sin cambio', () => {
    const f = toFriendly(SAMPLE_CONFIG);
    expect(f.retencion_dias_default).toBe(30);
  });
});

describe('toInternal', () => {
  it('convierte face_absent_seg a ms', () => {
    const friendly = toFriendly(SAMPLE_CONFIG);
    const internal = toInternal(friendly);
    expect(internal.face_absent_ms).toBe(3000);
  });

  it('pasa umbral_cola_revision sin cambio', () => {
    const friendly = toFriendly(SAMPLE_CONFIG);
    const internal = toInternal(friendly);
    expect(internal.umbral_cola_revision).toBe(70);
  });
});

describe('toFriendly → toInternal (round-trip completo)', () => {
  it('round-trip de valores ms preserva el orden de magnitud (dentro del bucket)', () => {
    const friendly = toFriendly(SAMPLE_CONFIG);
    const back = toInternal(friendly);
    // Los valores de ms deben coincidir exactamente (seg → ms es round-trip exacto)
    expect(back.face_absent_ms).toBe(SAMPLE_CONFIG.face_absent_ms);
    expect(back.gaze_sustained_ms).toBe(SAMPLE_CONFIG.gaze_sustained_ms);
    expect(back.umbral_cola_revision).toBe(SAMPLE_CONFIG.umbral_cola_revision);
    expect(back.retencion_dias_default).toBe(SAMPLE_CONFIG.retencion_dias_default);
    expect(back.multiple_faces_frames).toBe(SAMPLE_CONFIG.multiple_faces_frames);
  });

  it('el round-trip de sensibilidad preserva el BUCKET (no el valor exacto)', () => {
    // El valor exacto puede diferir (0.20 → "media" → 0.25) pero el label es el mismo
    const friendly = toFriendly(SAMPLE_CONFIG);
    const back = toInternal(friendly);
    // Verificamos que el round-trip de label se mantiene
    expect(gazeDeviationToLabel(back.gaze_deviation_threshold)).toBe(friendly.gaze_deviation_label);
    expect(gazeFixationToLabel(back.gaze_fixation_tolerance)).toBe(friendly.gaze_fixation_label);
  });

  it('config con sensibilidad "alta" — round-trip preserva el label', () => {
    const cfgAlta: ConfigInternal = { ...SAMPLE_CONFIG, gaze_deviation_threshold: 0.10, gaze_fixation_tolerance: 0.05 };
    const f = toFriendly(cfgAlta);
    expect(f.gaze_deviation_label).toBe('alta');
    expect(f.gaze_fixation_label).toBe('alta');
    const back = toInternal(f);
    expect(gazeDeviationToLabel(back.gaze_deviation_threshold)).toBe('alta');
    expect(gazeFixationToLabel(back.gaze_fixation_tolerance)).toBe('alta');
  });

  it('config con sensibilidad "baja" — round-trip preserva el label', () => {
    const cfgBaja: ConfigInternal = { ...SAMPLE_CONFIG, gaze_deviation_threshold: 0.50, gaze_fixation_tolerance: 0.40 };
    const f = toFriendly(cfgBaja);
    expect(f.gaze_deviation_label).toBe('baja');
    expect(f.gaze_fixation_label).toBe('baja');
    const back = toInternal(f);
    expect(gazeDeviationToLabel(back.gaze_deviation_threshold)).toBe('baja');
    expect(gazeFixationToLabel(back.gaze_fixation_tolerance)).toBe('baja');
  });
});
