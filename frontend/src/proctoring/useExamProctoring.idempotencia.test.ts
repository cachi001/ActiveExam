/**
 * Test de la GUARDA DE IDEMPOTENCIA de creación de sesión (C-64 / StrictMode).
 *
 * En dev con React.StrictMode el effect de arranque monta dos veces y, sin guarda,
 * `api.crearSesionProctoring` se dispara DOS veces antes de chequear `cancelled` →
 * se crean DOS sesiones. La guarda dedupe la creación por `examen.id` a nivel de
 * módulo: dos llamadas para el mismo examen reutilizan la MISMA promesa y, por lo
 * tanto, un solo POST. Llamadas para exámenes distintos NO se deduplican.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../lib/api';
import {
  obtenerOCrearSesion,
  __resetSesionEnCreacionParaTest,
} from './useExamProctoring';

describe('useExamProctoring — guarda de idempotencia de creación de sesión', () => {
  beforeEach(() => {
    __resetSesionEnCreacionParaTest();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    __resetSesionEnCreacionParaTest();
  });

  it('dispara UNA sola creación para dos llamadas del mismo examen (doble montaje StrictMode)', async () => {
    const spy = vi
      .spyOn(api, 'crearSesionProctoring')
      .mockResolvedValue({ id: 'sesion-1' } as Awaited<
        ReturnType<typeof api.crearSesionProctoring>
      >);

    const p1 = obtenerOCrearSesion('examen-A', 'Final Cálculo');
    const p2 = obtenerOCrearSesion('examen-A', 'Final Cálculo');

    // Misma promesa reutilizada: la segunda llamada NO crea una sesión nueva.
    expect(p1).toBe(p2);
    await expect(p1).resolves.toBe('sesion-1');
    await expect(p2).resolves.toBe('sesion-1');
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('crea sesiones independientes para exámenes distintos', async () => {
    const spy = vi
      .spyOn(api, 'crearSesionProctoring')
      .mockImplementation(
        async (_modo, _etiqueta, examId) =>
          ({ id: `sesion-${examId}` } as Awaited<
            ReturnType<typeof api.crearSesionProctoring>
          >),
      );

    const a = await obtenerOCrearSesion('examen-A', undefined);
    const b = await obtenerOCrearSesion('examen-B', undefined);

    expect(a).toBe('sesion-examen-A');
    expect(b).toBe('sesion-examen-B');
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it('libera la guarda si la creación falla, permitiendo reintentar', async () => {
    const spy = vi
      .spyOn(api, 'crearSesionProctoring')
      .mockRejectedValueOnce(new Error('red caída'))
      .mockResolvedValueOnce({ id: 'sesion-ok' } as Awaited<
        ReturnType<typeof api.crearSesionProctoring>
      >);

    // Primer intento: falla → la guarda se libera (devuelve null).
    await expect(obtenerOCrearSesion('examen-C', undefined)).resolves.toBeNull();
    // Segundo intento (montaje posterior): vuelve a crear porque la guarda se liberó.
    await expect(obtenerOCrearSesion('examen-C', undefined)).resolves.toBe('sesion-ok');
    expect(spy).toHaveBeenCalledTimes(2);
  });
});
