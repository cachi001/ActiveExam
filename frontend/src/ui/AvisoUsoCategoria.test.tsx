/**
 * AvisoUsoCategoria — lo que se le dice al docente ANTES de renombrar o dar de
 * baja una categoría del banco.
 *
 * La decisión es AVISAR, NO BLOQUEAR: renombrar o dar de baja una categoría no
 * cambia ninguna nota (las preguntas del examen están copiadas) ni saca
 * preguntas de un examen armado. Lo que se degrada es la trazabilidad de un
 * examen ya rendido. Por eso este componente informa y nunca deshabilita nada.
 *
 * Contrato de presentación puro: recibe el uso ya consultado, no llama a ningún
 * endpoint. El texto del aviso lo escribe el backend (es una regla del dominio,
 * la misma para los dos diálogos y para cualquier cliente de la API); acá se
 * agrega la lista de exámenes para que se vea CUÁLES son.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import { AvisoUsoCategoria } from './AvisoUsoCategoria';

const SIN_USO = {
  categoria_id: 'c1',
  nombre: 'Unidad 1',
  rama: ['c1'],
  examenes: [],
  total_examenes: 0,
  examenes_rendidos: 0,
  aviso: null,
};

afterEach(() => {
  cleanup();
});

describe('AvisoUsoCategoria', () => {
  it('mientras consulta lo dice, sin afirmar todavía que no pasa nada', () => {
    const { container } = render(<AvisoUsoCategoria uso={null} cargando />);
    expect(container.textContent).toMatch(/revisando/i);
  });

  it('no dice nada cuando la categoría no se usó en ningún examen', () => {
    const { container } = render(<AvisoUsoCategoria uso={SIN_USO} cargando={false} />);
    expect(container.textContent?.trim()).toBe('');
  });

  it('muestra el aviso del backend y CUÁLES son los exámenes', () => {
    render(
      <AvisoUsoCategoria
        cargando={false}
        uso={{
          ...SIN_USO,
          total_examenes: 2,
          examenes_rendidos: 1,
          aviso: '«Unidad 1» se usa en 2 exámenes y 1 ya se rindió.',
          examenes: [
            { examen_id: 'e1', titulo: 'Parcial 1', rendido: true },
            { examen_id: 'e2', titulo: 'Recuperatorio', rendido: false },
          ],
        }}
      />,
    );
    expect(screen.getByRole('note').textContent).toMatch(/ya se rindió/);
    expect(screen.getByText(/Parcial 1/)).toBeTruthy();
    expect(screen.getByText(/Recuperatorio/)).toBeTruthy();
  });

  it('distingue el examen ya rendido del que todavía no', () => {
    render(
      <AvisoUsoCategoria
        cargando={false}
        uso={{
          ...SIN_USO,
          total_examenes: 1,
          examenes_rendidos: 1,
          aviso: 'algo',
          examenes: [{ examen_id: 'e1', titulo: 'Parcial 1', rendido: true }],
        }}
      />,
    );
    expect(screen.getByText(/Parcial 1/).textContent).toMatch(/ya rendido/i);
  });

  it('si la consulta falla lo dice, en vez de callar como si no hubiera nada', () => {
    // Un aviso que se pierde en silencio es peor que no tenerlo: el docente
    // confirma creyendo que nadie usa la categoría.
    const { container } = render(
      <AvisoUsoCategoria uso={null} cargando={false} error="se cayó" />,
    );
    expect(container.textContent).toMatch(/no se pudo/i);
  });
});
