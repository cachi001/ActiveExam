/**
 * Tests — ExamenVivoGroup: las filas dicen QUIÉN está rindiendo.
 *
 * Encontrado el 2/9/2026 mirando el panel como tutor: la fila mostraba la
 * `etiqueta` de la sesión, que la manda el cliente y en el flujo real cae al
 * TÍTULO DEL EXAMEN cuando el nombre del alumno no está cargado. Con 40 personas
 * rindiendo, el tutor veía 40 filas que decían todas lo mismo.
 */
import { describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach } from 'vitest';
import { ExamenVivoGroup } from './ExamenVivoGroup';
import type { SesionProctoringResumen } from '../../lib/types';

afterEach(cleanup);

function sesion(extra: Partial<SesionProctoringResumen> = {}): SesionProctoringResumen {
  return {
    id: `s-${Math.random()}`,
    modo: 'examen',
    exam_id: 'ex-1',
    creada_en: new Date().toISOString(),
    total_eventos: 0,
    total_discrepancias: 0,
    score: 0,
    umbral_cola_revision_efectivo: 70,
    ...extra,
  } as SesionProctoringResumen;
}

const examInfo = {
  examNombre: 'Parcial 1 — Programación III',
  materiaNombre: 'Programación III',
  comisionNombre: 'Comisión 1',
};

describe('ExamenVivoGroup', () => {
  it('muestra el nombre de la persona, no el del examen', () => {
    render(
      <ExamenVivoGroup
        examInfo={examInfo}
        sesiones={[
          sesion({
            alumno_nombre: 'Ada Lovelace',
            alumno_email: 'ada@uni.edu',
            alumno_idnumber: 'lti:1:7',
            etiqueta: 'Parcial 1 — Programación III',
          }),
        ]}
        onAbrir={vi.fn()}
      />,
    );

    expect(screen.getByText('Ada Lovelace')).toBeTruthy();
    // El correo desambigua homónimos, que en una comisión pasan.
    expect(screen.getByText(/ada@uni\.edu/)).toBeTruthy();
    // Y el username interno NO se muestra: para quien entra por el campus es
    // "lti:1:7" y no le dice nada a nadie.
    expect(screen.queryByText(/lti:1:7/)).toBeNull();
  });

  it('dos personas distintas se ven distintas aunque compartan etiqueta', () => {
    // Es el caso que rompía la pantalla: la etiqueta la manda el cliente y puede
    // ser la misma para todos.
    render(
      <ExamenVivoGroup
        examInfo={examInfo}
        sesiones={[
          sesion({ alumno_nombre: 'Ada Lovelace', etiqueta: 'Parcial 1' }),
          sesion({ alumno_nombre: 'Grace Hopper', etiqueta: 'Parcial 1' }),
        ]}
        onAbrir={vi.fn()}
      />,
    );

    expect(screen.getByText('Ada Lovelace')).toBeTruthy();
    expect(screen.getByText('Grace Hopper')).toBeTruthy();
  });

  it('marca la sesión de prueba para no perseguir un fantasma', () => {
    render(
      <ExamenVivoGroup
        examInfo={examInfo}
        sesiones={[sesion({ alumno_nombre: 'Docente Que Ensaya', es_prueba: true })]}
        onAbrir={vi.fn()}
      />,
    );

    expect(screen.getByText(/Prueba/)).toBeTruthy();
  });

  it('una rendición real NO se marca como prueba', () => {
    render(
      <ExamenVivoGroup
        examInfo={examInfo}
        sesiones={[sesion({ alumno_nombre: 'Ada Lovelace', es_prueba: false })]}
        onAbrir={vi.fn()}
      />,
    );

    expect(screen.queryByText(/Prueba/)).toBeNull();
  });

  it('sin identidad del servidor cae a la etiqueta, sin romperse', () => {
    render(
      <ExamenVivoGroup
        examInfo={examInfo}
        sesiones={[sesion({ etiqueta: 'Juan Pérez' })]}
        onAbrir={vi.fn()}
      />,
    );

    expect(screen.getByText('Juan Pérez')).toBeTruthy();
  });
});
