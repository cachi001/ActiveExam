/**
 * La información de la comisión que ve el alumno tiene que salir de lo que el
 * backend manda de verdad.
 *
 * ## El defecto
 *
 * La fila leía `comision.docente` y `comision.horario`: dos campos del modelo
 * VIEJO (docente 1:1) que el backend dejó de mandar cuando los tutores pasaron a
 * ser N:M en c-79. Hoy manda `tutores: [{id, nombre}]`, que la pantalla ignoraba.
 *
 * Resultado: el alumno abría una comisión con tutor asignado y no veía ningún
 * tutor. Y como `periodo`/`anio` suelen venir vacíos, con frecuencia caía en
 * "Todavía no hay información adicional de esta comisión" teniendo la info.
 *
 * Verificado el 29/8/2026 contra la API: `GET /materias/{id}/comisiones`
 * devuelve `tutores` con «Tutor Prueba» y ningún `docente` ni `horario`.
 */

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { ComisionRow } from './ComisionRow';
import type { Comision } from '../../../lib/types';

afterEach(() => cleanup());

const comision = (extra: Partial<Comision> = {}): Comision =>
  ({
    id: 'c-1',
    materia_id: 'm-1',
    nombre: 'Comisión 1 (mañana)',
    codigo: 'C-DEMO',
    activa: true,
    ...extra,
  }) as Comision;

const montar = (c: Comision) =>
  render(
    <ComisionRow
      comision={c}
      activa
      cargandoExamenes={false}
      examenes={[]}
      onSelect={() => {}}
      onIrAExamenes={() => {}}
    />,
  );

describe('ComisionRow — información de la comisión', () => {
  it('muestra el tutor a cargo', () => {
    montar(comision({ tutores: [{ id: 't-1', nombre: 'Tutor Prueba' }] }));
    // Aparece dos veces a propósito: en el resumen de la fila y en el detalle.
    expect(screen.queryAllByText(/Tutor Prueba/).length).toBeGreaterThan(0);
  });

  it('lista los varios tutores cuando hay más de uno', () => {
    // Desde c-79 una comisión puede tener varios: mostrar solo el primero
    // escondería a quien efectivamente acompaña al alumno.
    montar(
      comision({
        tutores: [
          { id: 't-1', nombre: 'Ana Gómez' },
          { id: 't-2', nombre: 'Luis Paz' },
        ],
      }),
    );
    expect(screen.queryAllByText(/Ana Gómez/).length).toBeGreaterThan(0);
    expect(screen.queryAllByText(/Luis Paz/).length).toBeGreaterThan(0);
  });

  it('con varios tutores la etiqueta va en plural', () => {
    montar(
      comision({
        tutores: [
          { id: 't-1', nombre: 'Ana Gómez' },
          { id: 't-2', nombre: 'Luis Paz' },
        ],
      }),
    );
    expect(screen.getByText(/^Tutores:/)).toBeTruthy();
  });

  it('sin tutor asignado no inventa uno', () => {
    montar(comision({ tutores: [] }));
    expect(screen.queryByText(/^Tutor(es)?:/)).toBeNull();
  });

  it('no dice que no hay información cuando sí la hay', () => {
    // El síntoma que reportó el dueño: comisión con tutor y código, y el cartel
    // de "todavía no hay información" igual.
    montar(comision({ tutores: [{ id: 't-1', nombre: 'Tutor Prueba' }] }));
    expect(screen.queryByText(/todavía no hay información/i)).toBeNull();
  });

  it('el tutor también aparece en el resumen de la fila cerrada', () => {
    render(
      <ComisionRow
        comision={comision({ tutores: [{ id: 't-1', nombre: 'Tutor Prueba' }] })}
        activa={false}
        cargandoExamenes={false}
        examenes={[]}
        onSelect={() => {}}
        onIrAExamenes={() => {}}
      />,
    );
    expect(screen.getByText(/Tutor Prueba/)).toBeTruthy();
  });

  it('muestra el código de la comisión', () => {
    montar(comision({ tutores: [] }));
    expect(screen.queryAllByText(/C-DEMO/).length).toBeGreaterThan(0);
  });
});
