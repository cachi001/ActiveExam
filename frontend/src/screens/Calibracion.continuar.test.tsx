/**
 * El botón «Continuar» no compite con el de calibrar.
 *
 * Bug real (29/8/2026): mientras la calibración medía, la pantalla mostraba DOS
 * botones diciendo lo mismo — el de la tarjeta («Calibrando… 4s») y el de abajo,
 * que cambiaba su texto a «Calibrando…» y quedaba deshabilitado. Un botón apagado
 * que repite el cartel del de arriba no informa nada y ensucia el paso.
 *
 * «Continuar» aparece cuando hay algo que continuar. Mientras mide, no.
 *
 * Sin @testing-library (no está instalado): createRoot + act.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';

import type { EstadoCalibracion } from './examen/CalibracionPaso';

const { estadoMock } = vi.hoisted(() => ({ estadoMock: { valor: 'pendiente' as EstadoCalibracion } }));

// La tarjeta real enciende la cámara al montar; acá solo interesa el botón de abajo.
vi.mock('./examen/CalibracionPaso', () => ({
  CalibracionPaso: ({ onEstado }: { onEstado: (e: EstadoCalibracion) => void }) => {
    // Empuja el estado que el caso quiere probar, como haría la tarjeta real.
    queueMicrotask(() => onEstado(estadoMock.valor));
    return createElement('div', null, 'tarjeta de calibración');
  },
}));

vi.mock('../lib/router', () => ({ useNavigate: () => vi.fn() }));

vi.mock('../ui/shells', () => ({
  StudentShell: ({ children }: { children: unknown }) => createElement('div', null, children),
}));

let container: HTMLDivElement;
let root: Root;

async function montar(estado: EstadoCalibracion): Promise<string> {
  estadoMock.valor = estado;
  const Calibracion = (await import('./Calibracion')).default;
  await act(async () => {
    root.render(createElement(Calibracion));
  });
  await act(async () => {});
  return container.textContent ?? '';
}

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

describe('botón Continuar del paso de calibración', () => {
  it('mientras mide NO muestra Continuar', () => {
    // Es el caso del bug: dos botones diciendo «Calibrando…» al mismo tiempo.
    return montar('midiendo').then((texto) => {
      expect(texto).not.toContain('Continuar');
      expect(texto).not.toContain('Calibrando…');
    });
  });

  it('cuando la calibración terminó bien, muestra Continuar', async () => {
    const texto = await montar('lista');
    expect(texto).toContain('Continuar');
  });

  // CAMBIO DE DECISIÓN (dueño, 6/9/2026): la calibración pasa a ser OBLIGATORIA.
  // Antes se dejaba pasar sin calibrar con el criterio de "perder precisión es
  // menos grave que trabar a alguien en el ingreso". El costo de ese criterio se
  // vio en la práctica: sin calibrar, la mirada se mide contra el centro de la
  // CÁMARA, o sea que el sistema espera que el alumno mire al lente mientras
  // rinde. Eso produce eventos de mirada desviada por leer normalmente.
  //
  // Trabar a alguien sin cámara no agrega un bloqueo nuevo: la cámara ya es
  // obligatoria para rendir (el chequeo de requisitos no deja pasar sin ella).
  it('sin cámara NO deja continuar', async () => {
    const texto = await montar('sin_camara');
    expect(texto).not.toContain('Continuar');
  });

  it('antes de calibrar NO deja continuar', async () => {
    const texto = await montar('pendiente');
    expect(texto).not.toContain('Continuar');
  });

  it('sin calibrar explica por qué no puede seguir', async () => {
    const texto = await montar('pendiente');
    expect(texto).toContain('Calibrá para continuar');
  });

  // 'fallida' (calibración de 4 puntos incompleta: se salió de pantalla completa,
  // o no midió una esquina) es tan bloqueante como 'sin_camara': la cámara andaba
  // bien, pero no hay baseline confiable con el que rendir.
  it('calibración fallida NO deja continuar', async () => {
    const texto = await montar('fallida');
    expect(texto).not.toContain('Continuar');
  });

  it('calibración fallida explica por qué no puede seguir', async () => {
    const texto = await montar('fallida');
    expect(texto).toContain('Calibrá para continuar');
  });
});
