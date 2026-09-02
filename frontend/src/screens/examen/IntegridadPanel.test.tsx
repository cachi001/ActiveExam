/**
 * Panel de Supervisión del examen: qué ve el alumno cuando el examen tiene
 * prendido `mostrar_eventos_alumno`.
 *
 * Decisión del dueño (30/8/2026): con la opción prendida se ven TODOS los
 * eventos que se generaron, no solo los más recientes. Antes el panel cortaba
 * en los 4 últimos y dejaba un "+N más" que era texto muerto: el alumno no
 * tenía forma de ver el resto, y el puntaje total no cerraba con lo que la
 * lista mostraba.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { IntegridadPanel } from './IntegridadPanel';
import type { EventoSesion } from '../../lib/types';

afterEach(cleanup);

vi.mock('../../config/effectiveConfigCache', () => ({
  getEffectiveConfig: () => null,
}));

function evento(n: number, severidad: EventoSesion['severidad'] = 'media'): EventoSesion {
  return {
    id: `ev-${n}`,
    tipo: 'cambio_pestana',
    severidad,
    ts_backend: new Date().toISOString(),
    descripcion: `evento ${n}`,
    tiene_evidencia: false,
  } as EventoSesion;
}

/** Filas de evento del panel (cada una es una tarjeta con borde). */
function filasDeEvento(container: HTMLElement): NodeListOf<Element> {
  return container.querySelectorAll('[data-testid="evento-supervision"]');
}

describe('IntegridadPanel — detalle prendido', () => {
  it('muestra TODOS los eventos generados, no solo los últimos', () => {
    const eventos = Array.from({ length: 10 }, (_, i) => evento(i));
    const { container } = render(
      <IntegridadPanel activo eventCount={10} score={45} eventos={eventos} examen={null} mostrarEventos />,
    );

    expect(filasDeEvento(container)).toHaveLength(10);
  });

  it('con un solo evento muestra ese evento', () => {
    const { container } = render(
      <IntegridadPanel activo eventCount={1} score={20} eventos={[evento(0)]} examen={null} mostrarEventos />,
    );

    expect(filasDeEvento(container)).toHaveLength(1);
  });

  it('ya no queda el "+N más" que no llevaba a ninguna parte', () => {
    const eventos = Array.from({ length: 10 }, (_, i) => evento(i));
    render(
      <IntegridadPanel activo eventCount={10} score={45} eventos={eventos} examen={null} mostrarEventos />,
    );

    expect(screen.queryByText(/\+\d+ más/)).toBeNull();
  });

  it('la lista scrollea en vez de estirar la pantalla del examen', () => {
    const eventos = Array.from({ length: 40 }, (_, i) => evento(i));
    const { container } = render(
      <IntegridadPanel activo eventCount={40} score={100} eventos={eventos} examen={null} mostrarEventos />,
    );

    const lista = container.querySelector('[data-testid="lista-eventos-supervision"]');
    expect(lista).not.toBeNull();
    expect(lista!.className).toMatch(/overflow-y-auto/);
    expect(filasDeEvento(container)).toHaveLength(40);
  });

  it('sin incidencias avisa que no hay nada registrado', () => {
    const { container } = render(
      <IntegridadPanel activo eventCount={0} score={0} eventos={[]} examen={null} mostrarEventos />,
    );

    expect(filasDeEvento(container)).toHaveLength(0);
    expect(container.textContent).toContain('Sin incidencias');
  });
});

describe('IntegridadPanel — detalle apagado', () => {
  it('no muestra ni los eventos ni el puntaje', () => {
    const eventos = Array.from({ length: 10 }, (_, i) => evento(i));
    const { container } = render(
      <IntegridadPanel activo eventCount={10} score={45} eventos={eventos} examen={null} />,
    );

    expect(filasDeEvento(container)).toHaveLength(0);
    expect(container.textContent).not.toContain('45 pts');
    expect(container.textContent).toContain('Activa');
  });
});
