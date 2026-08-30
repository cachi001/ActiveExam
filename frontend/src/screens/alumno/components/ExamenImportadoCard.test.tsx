/**
 * La card de un examen disponible: qué promete el botón y hasta cuándo se rinde.
 *
 * El botón decía "Rendir", pero lleva a `/pre-examen`, que es la ficha del
 * examen y tiene su propio "Comenzar examen". El alumno hacía click esperando
 * arrancar y aterrizaba en otra pantalla con otro botón. Decisión del dueño
 * (28/8/2026): que diga lo que hace.
 *
 * Y la card no decía nada de la ventana de rendición: el gate solo nombra la
 * fecha cuando BLOQUEA, así que un examen disponible no mostraba hasta cuándo
 * lo estaba.
 */

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { ExamenImportadoCard } from './ExamenImportadoCard';
import type { GateImportado } from '../gateExamenImportado';
import type { ExamenContenidoResumen } from '../../../lib/types';

afterEach(() => cleanup());

const contenido = (extra: Partial<ExamenContenidoResumen> = {}): ExamenContenidoResumen =>
  ({
    id: 'EX-1',
    titulo: 'Parcial U1-U3 — completar código',
    cantidad_preguntas: 10,
    tiempo_limite_min: 45,
    apertura: null,
    cierre: null,
    ...extra,
  }) as ExamenContenidoResumen;

const HABILITADO: GateImportado = { habilitado: true, usados: 0, permitidos: null };

const montar = (
  c: ExamenContenidoResumen,
  gate: GateImportado = HABILITADO,
  perfilCompleto = true,
) =>
  render(
    <ExamenImportadoCard
      contenido={c}
      rindiendo={false}
      gate={gate}
      perfilCompleto={perfilCompleto}
      onRendir={() => {}}
      onCompletarPerfil={() => {}}
    />,
  );

describe('ExamenImportadoCard', () => {
  it('no le dice al alumno cuántas preguntas tiene el examen', () => {
    // Decisión del dueño (28/8/2026): la cantidad de preguntas no se le muestra
    // al alumno en ninguna pantalla previa a rendir.
    montar(contenido());
    expect(screen.queryByText(/pregunta/i)).toBeNull();
  });

  it('sigue mostrando el tiempo, que el alumno necesita para organizarse', () => {
    montar(contenido());
    expect(screen.getByText(/45 min/)).toBeTruthy();
  });

  it('el botón no promete que se empieza a rendir', () => {
    montar(contenido());
    expect(screen.getByRole('button').textContent).toContain('Ver examen');
    expect(screen.queryByText(/^Rendir$/)).toBeNull();
  });

  it('muestra la ventana de rendición con las dos fechas', () => {
    montar(
      contenido({ apertura: '2026-08-27T12:00:00Z', cierre: '2026-08-31T02:59:00Z' }),
    );
    // Etiquetas explícitas y en renglones propios: el alumno tiene que poder
    // distinguir cuál fecha es cuál sin leer una frase corrida.
    expect(screen.getByText('Desde')).toBeTruthy();
    expect(screen.getByText('Hasta')).toBeTruthy();
    // Con año y con "hs": una hora suelta al lado de una fecha no se lee como hora.
    // getAllByText: ahora hay DOS fechas, una por renglón.
    expect(screen.getAllByText(/2026, \d{2}:\d{2} hs/)).toHaveLength(2);
  });

  it('con solo cierre dice hasta cuándo, y avisa que no hay inicio', () => {
    montar(contenido({ cierre: '2026-08-31T02:59:00Z' }));
    expect(screen.getByText('Hasta')).toBeTruthy();
    expect(screen.getByText(/Sin fecha de inicio/i)).toBeTruthy();
  });

  it('sin fechas configuradas no inventa una ventana', () => {
    // Dice "Sin fecha de cierre", que es información; lo que no puede hacer es
    // mostrar un rango que nadie configuró.
    montar(contenido());
    expect(screen.getByText(/Sin fecha de inicio/i)).toBeTruthy();
    expect(screen.getByText(/Sin fecha de cierre/i)).toBeTruthy();
  });

  it('sin perfil completo el botón manda a completarlo, no al examen', () => {
    montar(contenido(), HABILITADO, false);
    expect(screen.getByRole('button').textContent).toContain('Completar perfil');
  });

  it('mientras verifica, el botón lo dice', () => {
    render(
      <ExamenImportadoCard
        contenido={contenido()}
        rindiendo
        gate={HABILITADO}
        perfilCompleto
        onRendir={() => {}}
        onCompletarPerfil={() => {}}
      />,
    );
    expect(screen.getByRole('button').textContent).toContain('Verificando');
  });
});

// ---------------------------------------------------------------------------
// Prioridad del mensaje cuando falta el perfil Y el examen está bloqueado
// ---------------------------------------------------------------------------
//
// Visto el 28/8/2026 en el listado real: un examen ya cerrado (27-ago 22:49)
// mostraba "Completá tu perfil para poder rendir" y escondía que estaba cerrado.
// El alumno completa todo el enrollment y recién entonces descubre que ese
// examen no se puede rendir. El motivo del bloqueo tiene que ganar: completar el
// perfil no lo vuelve rendible.

describe('ExamenImportadoCard — qué mensaje gana', () => {
  const BLOQUEADO: GateImportado = {
    habilitado: false,
    motivo: 'Cerrado el 27/08/2026 22:49',
    usados: 0,
    permitidos: null,
  };

  it('con el examen cerrado muestra el cierre, no el perfil', () => {
    montar(contenido(), BLOQUEADO, false);
    expect(screen.getByText(/cerrado el/i)).toBeTruthy();
    expect(screen.queryByText(/completá tu perfil/i)).toBeNull();
  });

  it('y no ofrece un botón que no lleva a ningún lado', () => {
    // "Completar perfil" ahí es trabajo inútil: el examen sigue cerrado después.
    montar(contenido(), BLOQUEADO, false);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('si el examen está disponible, sí pide completar el perfil', () => {
    montar(contenido(), HABILITADO, false);
    expect(screen.getByText(/completá tu perfil/i)).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Qué información muestra la tarjeta
// ---------------------------------------------------------------------------
//
// Reportado por el dueño el 29/8/2026: los exámenes de desarrollo no tienen
// fechas ni tiempo límite cargados, así que la tarjeta quedaba con UNA sola
// línea debajo del título — "Te queda 1 de 1 intento" — que además confunde:
// en un examen de un solo intento no hay nada que "quede".
//
// La API ya manda materia y comisión, que no se estaban usando.

describe('ExamenImportadoCard — información visible', () => {
  it('dice a qué materia y comisión pertenece', () => {
    montar(
      contenido({
        materia_nombre: 'Análisis Matemático I',
        comision_nombre: 'Comisión 1 (mañana)',
      }),
    );
    expect(screen.getByText(/Análisis Matemático I/)).toBeTruthy();
    expect(screen.getByText(/Comisión 1 \(mañana\)/)).toBeTruthy();
  });

  it('con un solo intento no habla de intentos "restantes"', () => {
    montar(contenido(), { habilitado: true, usados: 0, permitidos: 1 });
    expect(screen.queryByText(/te queda/i)).toBeNull();
  });

  it('con un solo intento avisa que no hay segunda chance', () => {
    montar(contenido(), { habilitado: true, usados: 0, permitidos: 1 });
    expect(screen.getByText(/un solo intento/i)).toBeTruthy();
  });

  it('con varios intentos sí dice cuántos quedan', () => {
    montar(contenido(), { habilitado: true, usados: 1, permitidos: 3 });
    expect(screen.getByText(/quedan 2 de 3/i)).toBeTruthy();
  });

  it('sin tiempo límite lo dice, en vez de callarse', () => {
    montar(contenido({ tiempo_limite_min: null }));
    expect(screen.getByText(/sin límite de tiempo/i)).toBeTruthy();
  });

  it('sin fecha de cierre lo dice, para que el alumno no lo suponga', () => {
    montar(contenido({ apertura: null, cierre: null }));
    expect(screen.getByText(/sin fecha de cierre/i)).toBeTruthy();
  });

  it('con fecha de cierre muestra la fecha y no el "sin fecha"', () => {
    montar(contenido({ cierre: '2026-08-31T02:59:00Z' }));
    expect(screen.getByText(/2026, \d{2}:\d{2} hs/)).toBeTruthy();
    expect(screen.queryByText(/sin fecha de cierre/i)).toBeNull();
  });
});

describe('chip de examen de prueba (migración 0105)', () => {
  it('un examen en modo prueba lo muestra', () => {
    montar(contenido({ modo_prueba: true }));
    expect(screen.getByText('Examen de prueba')).toBeTruthy();
  });

  it('un examen normal NO lo muestra', () => {
    // El contrapeso: sin esto, un chip pegado siempre pasaría el test de arriba.
    montar(contenido({ modo_prueba: false }));
    expect(screen.queryByText(/Examen de prueba/)).toBeNull();
  });
});
