/**
 * El alumno que se cayó tiene que ver que su examen sigue abierto.
 *
 * Caso real (29/8/2026, el dueño rindiendo): se le cortó el wifi en medio del
 * examen, salió, y al volver esta tarjeta le mostró el examen igual que si nunca
 * lo hubiera empezado, con el cartel "Tenés un solo intento". Entendió que había
 * gastado el intento y no se animó a entrar. Su sesión seguía viva: el backend
 * reanuda la misma sesión con su cronómetro y le restaura las respuestas, y el
 * conteo de intentos solo cuenta las sesiones FINALIZADAS.
 *
 * Lo que faltaba era decírselo. Estos tests fijan las dos mitades: que el aviso
 * aparezca cuando hay algo abierto, y que el cartel de intentos NO aparezca ahí
 * (es el que le hizo creer que lo había perdido).
 *
 * Sin @testing-library (no está instalado): createRoot + act, mismo patrón que
 * Examen.calibracionMirada.test.tsx.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';

import { ExamenImportadoCard } from './ExamenImportadoCard';
import type { ExamenContenidoResumen } from '../../../lib/types';
import type { SesionEnCurso } from '../../../lib/apiProctoring/sesion';

const CONTENIDO = {
  id: 'ex-1',
  titulo: 'Parcial U1-U3',
  cantidad_preguntas: 10,
  materia_nombre: 'Análisis Matemático I',
  comision_nombre: 'Comisión 1',
  apertura: null,
  cierre: null,
  tiempo_limite_min: null,
  intentos_permitidos: 1,
} as unknown as ExamenContenidoResumen;

const GATE_OK = { habilitado: true, permitidos: 1, usados: 0 } as never;

const SESION: SesionEnCurso = {
  session_id: 'sess-1',
  examen_contenido_id: 'ex-1',
  examen_titulo: 'Parcial U1-U3',
  creada_en: '2026-08-29T08:11:41Z',
  examen_iniciado_en: '2026-08-29T08:11:45Z',
};

let container: HTMLDivElement;
let root: Root;

function montar(props: Partial<Parameters<typeof ExamenImportadoCard>[0]>) {
  act(() => {
    root.render(
      createElement(ExamenImportadoCard, {
        contenido: CONTENIDO,
        rindiendo: false,
        gate: GATE_OK,
        perfilCompleto: true,
        onRendir: () => {},
        onCompletarPerfil: () => {},
        ...props,
      } as Parameters<typeof ExamenImportadoCard>[0]),
    );
  });
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

describe('examen dejado a medias', () => {
  it('sin sesión abierta, la tarjeta ofrece empezar como siempre', () => {
    const texto = montar({ sesionEnCurso: null });
    expect(texto).toContain('Ver examen');
    expect(texto).not.toContain('Continuar');
  });

  it('con sesión abierta, ofrece continuar en vez de empezar', () => {
    const texto = montar({ sesionEnCurso: SESION });
    expect(texto).toContain('Continuar');
    expect(texto).not.toContain('Ver examen');
  });

  it('con sesión abierta avisa que el examen quedó empezado', () => {
    // Sin este aviso el alumno no tiene forma de saber que lo que ve es su
    // examen a medias y no uno nuevo.
    const texto = montar({ sesionEnCurso: SESION });
    expect(texto.toLowerCase()).toContain('empezado');
  });

  it('con sesión abierta NO muestra el cartel de intentos', () => {
    // Es el cartel que le hizo creer que había gastado el intento. Continuar una
    // sesión abierta no consume ninguno: el enforcement solo cuenta finalizadas.
    const texto = montar({ sesionEnCurso: SESION });
    expect(texto).not.toContain('Tenés un solo intento');
  });

  it('sin sesión abierta el cartel de intentos se sigue mostrando', () => {
    // No se cayó de rebote: el alumno que todavía no empezó SÍ tiene que saber
    // que no va a poder repetirlo.
    const texto = montar({ sesionEnCurso: null });
    expect(texto).toContain('Tenés un solo intento');
  });
});
