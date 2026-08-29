/**
 * La tarjeta de una nota tiene que verse como el resto de las de la pantalla.
 *
 * Era la única fila de "Mis exámenes" sin el cuadro de icono a la izquierda:
 * `InscripcionCard` y `ExamenImportadoCard` lo tienen, esta no, así que al lado
 * de ellas se leía como un renglón suelto en vez de una tarjeta. Tampoco decía
 * cuándo se rindió el examen, con lo cual solo tenía una línea de contenido.
 */

import { MemoryRouter } from 'react-router-dom';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { NotaCard } from './NotaCard';
import type { NotaExamen } from '../../../lib/types';

const nota = (extra: Partial<NotaExamen> = {}): NotaExamen =>
  ({
    examen_id: 'ex-1',
    examen_titulo: 'Primer parcial — Límites y continuidad',
    nota: 42,
    nota_maxima: 100,
    estado_moodle: 'pendiente',
    en_cola_revision: false,
    score: null,
    umbral_revision: null,
    eventos: 0,
    finalizada_en: '2026-08-28T17:30:00Z',
    resultado: 'desaprobado',
    nota_visible: true,
    ...extra,
  }) as NotaExamen;

const montar = (n: NotaExamen) =>
  render(
    <MemoryRouter>
      <NotaCard nota={n} />
    </MemoryRouter>,
  );

// El proyecto no usa `globals: true`, así que el cleanup no es automático: sin
// esto cada render se acumula en el DOM y las queries encuentran duplicados.
afterEach(() => cleanup());

describe('NotaCard', () => {
  it('muestra el icono del examen, como las demás tarjetas de la pantalla', () => {
    montar(nota());
    expect(screen.getByText('assignment_turned_in')).toBeTruthy();
  });

  it('dice cuándo se rindió', () => {
    montar(nota());
    // Formato es-AR: día y mes abreviado. Sin esto la tarjeta tenía una sola línea.
    expect(screen.getByText(/rendido el/i)).toBeTruthy();
  });

  it('escribe la hora en 24 horas, sin el "p. m." de es-AR', () => {
    montar(nota());
    const fecha = screen.getByText(/rendido el/i).textContent ?? '';
    expect(fecha).not.toMatch(/[ap]\.\s?m\./i);
  });

  it('no inventa una fecha cuando el examen no tiene fin registrado', () => {
    montar(nota({ finalizada_en: null }));
    expect(screen.queryByText(/rendido el/i)).toBeNull();
  });

  it('sigue mostrando el título y la nota', () => {
    montar(nota());
    expect(screen.queryAllByText(/límites y continuidad/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/42 \/ 100/)).toBeTruthy();
  });
});

describe('NotaCard — qué estado gana en el chip', () => {
  it('en revisión gana sobre "disponible al cerrar"', () => {
    // Las dos cosas son ciertas a la vez (la nota no se ve todavía Y la sesión
    // entró a revisión), pero el chip decía "Disponible al cerrar" mientras el
    // texto de abajo explicaba la revisión: dos mensajes distintos sobre lo
    // mismo. Manda el más específico.
    montar(nota({ nota_visible: false, en_cola_revision: true }));
    expect(screen.getByText(/en revisión/i)).toBeTruthy();
    expect(screen.queryByText(/disponible al cerrar/i)).toBeNull();
  });

  it('sin revisión sí dice cuándo estará disponible', () => {
    montar(nota({ nota_visible: false, en_cola_revision: false }));
    expect(screen.getByText(/disponible al cerrar/i)).toBeTruthy();
  });

  it('una nota anulada no se muestra como "en revisión"', () => {
    montar(nota({ nota_visible: false, en_cola_revision: true, nota_anulada: true }));
    expect(screen.queryByText(/^En revisión$/i)).toBeNull();
  });
});
