import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

/**
 * C-72 sección 10 — Guardrails del EXPEDIENTE (Registro de sesión).
 *
 * El nombre viejo "Sesiones grabadas" invitaba a la interpretación PELIGROSA de que
 * hay grabación de video. NO la hay (RN-CC-01 / RN-CO-03): el expediente es evidencia
 * revisable (screenshots discretos + eventos + chat + anotaciones + biometría), NO un
 * video. Estos tests son un candado contra esa regresión y contra que alguien saque
 * piezas del expediente sin querer.
 */

const AQUI = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(AQUI, '..', '..'); // frontend/src

function leer(rel: string): string {
  return readFileSync(resolve(SRC, rel), 'utf8');
}

// Archivos que componen el expediente (ambos tipos de sesión) + su lista.
const ARCHIVOS_EXPEDIENTE = [
  'screens/ProctoringSessionDetail.tsx',
  'screens/SessionDetail.tsx',
  'screens/ProctoringRevisor.tsx',
  'screens/proctoring/DetalleHeader.tsx',
  'screens/proctoring/EventoCard.tsx',
  'screens/proctoring/BiometriaCard.tsx',
  'screens/proctoring/ObservacionesTutor.tsx',
  'screens/proctoring/PausaSesionPanel.tsx',
  'screens/proctoring/PausasHistorial.tsx',
  'ui/ChatBox.tsx',
];

// APIs / señales de GRABACIÓN DE VIDEO — ninguna debe aparecer en el expediente.
const APIS_DE_VIDEO = [
  'MediaRecorder',
  'captureStream',
  'requestVideoFrameCallback',
  'video_library', // icono engañoso (sugiere grabación); se reemplazó por `groups`.
];

describe('Expediente — guardrail contra grabación de video (C-72 sección 10.5)', () => {
  for (const rel of ARCHIVOS_EXPEDIENTE) {
    it(`${rel} no referencia ninguna API/ícono de grabación de video`, () => {
      const src = leer(rel);
      for (const marca of APIS_DE_VIDEO) {
        expect(src.includes(marca), `${rel} contiene "${marca}"`).toBe(false);
      }
    });
  }
});

describe('Expediente de EXAMEN — cobertura (C-72 sección 10.2)', () => {
  const src = leer('screens/ProctoringSessionDetail.tsx');

  it('incluye eventos con screenshot (EventoCard)', () => {
    expect(src).toContain('EventoCard');
  });
  it('incluye el chat con el estudiante (ChatBox)', () => {
    expect(src).toContain('ChatBox');
  });
  it('incluye las anotaciones del tutor (ObservacionesTutor)', () => {
    expect(src).toContain('ObservacionesTutor');
  });
  it('incluye la biometría', () => {
    expect(src).toContain('BiometriaCard');
  });
});

describe('Expediente de TEST/revisión — cobertura (C-72 sección 10.3)', () => {
  const src = leer('screens/SessionDetail.tsx');

  it('incluye statcards y eventos', () => {
    expect(src).toContain('StatCard');
    expect(src).toContain('sel.eventos');
  });
  // El expediente de test NO exige chat ni anotaciones del proctor (no aplican a una
  // rendición de prueba); no se testea su presencia — solo que no rompa el guardrail.
});
