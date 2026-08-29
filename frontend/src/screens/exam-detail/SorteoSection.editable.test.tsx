/**
 * Con el examen ya rendido no se ofrece editar las preguntas.
 *
 * Caso real (29/8/2026, "Segundo parcial — sorteado"): el examen tenía un intento
 * finalizado y la pantalla igual mostraba «Editar preguntas». El dueño lo dijo
 * derecho: "me deja editar las preguntas, algo que no tiene sentido".
 *
 * El backend SÍ lo rechaza (`PUT /{id}/sorteo` responde 409 ante cualquier sesión
 * real), y la propia respuesta ya traía `pool_editable: false` — el mismo campo que
 * la sección usaba para esconder el botón de «Incorporarlas al examen». El botón de
 * editar era el único que no lo miraba. Resultado: el tutor armaba todo el cambio y
 * recién al guardar se comía un rechazo, o peor, creía que había quedado guardado.
 *
 * Ofrecer una acción que el servidor va a rechazar no es un problema estético: hace
 * dudar de si el examen que los alumnos rindieron es el que está viendo.
 *
 * Sin @testing-library (no está instalado): createRoot + act.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';

import type { SorteoDelExamen } from '../../lib/examContentCatalog';

const SORTEO_BASE: SorteoDelExamen = {
  modo_preguntas: 'sorteo_por_intento',
  tramos: [
    {
      categoria_id: 'cat-1',
      categoria_nombre: 'Unidad 1',
      incluir_subcategorias: false,
      tipos: null,
      cantidad: 5,
      en_el_pool: 8,
      en_el_banco: 8,
    },
  ],
  largo_del_examen: 5,
  pool_total: 8,
  pool_banco_ids: [],
  nuevas_en_el_banco: 0,
  pool_editable: true,
  total_intentos: 0,
};

const { leerSorteoMock } = vi.hoisted(() => ({ leerSorteoMock: vi.fn() }));

vi.mock('../../lib/examContentCatalog', async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  leerSorteoDelExamenFn: leerSorteoMock,
  rearmarSorteoDelExamenFn: vi.fn(),
  actualizarPoolDelExamenFn: vi.fn(),
}));

// El componente usa el toast por contexto; sin provider explota al montar.
vi.mock('../../ui/toast', () => ({
  useToast: () => ({ error: vi.fn(), success: vi.fn(), info: vi.fn() }),
}));

let container: HTMLDivElement;
let root: Root;

async function montar(sorteo: SorteoDelExamen): Promise<string> {
  leerSorteoMock.mockResolvedValue(sorteo);
  const { SorteoSection } = await import('./SorteoSection');
  await act(async () => {
    root.render(createElement(SorteoSection, { examenId: 'ex-1', materiaId: 'mat-1' } as never));
  });
  return container.textContent ?? '';
}

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  leerSorteoMock.mockReset();
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

describe('editar las preguntas del sorteo', () => {
  it('sin intentos rendidos ofrece editar', async () => {
    const texto = await montar({ ...SORTEO_BASE, pool_editable: true, total_intentos: 0 });
    expect(texto).toContain('Editar preguntas');
  });

  it('con un intento rendido NO ofrece editar', async () => {
    // El backend lo rechaza igual; acá se deja de prometer lo que no se puede hacer.
    const texto = await montar({ ...SORTEO_BASE, pool_editable: false, total_intentos: 1 });
    expect(texto).not.toContain('Editar preguntas');
  });

  it('con un intento rendido explica por qué no se puede', async () => {
    // Esconder el botón sin decir nada se lee como que la pantalla está rota.
    const texto = await montar({ ...SORTEO_BASE, pool_editable: false, total_intentos: 1 });
    expect(texto.toLowerCase()).toContain('ya se rindió');
  });
});
