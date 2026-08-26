/**
 * AvisoSinResponsable — c-78 §18.4.
 *
 * En producción (26/8/2026) las tres materias estaban sin profesor y sin
 * coordinador, y las cinco comisiones sin tutor. Nada lo advertía: se podía
 * crear la estructura, importar exámenes y hacer rendir a los alumnos, y recién
 * al querer devolver las notas al campus aparecía el bloqueo `sin_docente`.
 *
 * Estos tests fijan las dos cosas que el aviso tiene que hacer bien: avisar
 * cuando falta alguien, y CALLARSE cuando no falta o cuando no se sabe. Un
 * cartel rojo permanente se vuelve parte del decorado y deja de avisar nada.
 */
import { afterEach, describe, it, expect } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AvisoSinResponsable } from './AvisoSinResponsable';

afterEach(() => {
  cleanup();
});

describe('AvisoSinResponsable — comisión sin tutor', () => {
  it('avisa que las notas no van a poder devolverse al campus', () => {
    render(<AvisoSinResponsable sinTutor nombre="Comisión 1A" />);
    const aviso = screen.getByRole('alert');
    expect(aviso.textContent).toMatch(/no se van a poder devolver al campus/i);
  });

  it('nombra a quién hay que asignar, para que se sepa qué hacer', () => {
    render(<AvisoSinResponsable sinTutor nombre="Comisión 1A" />);
    expect(screen.getByRole('alert').textContent).toMatch(/tutor/i);
  });

  it('no dice nada cuando la comisión SÍ tiene tutor', () => {
    const { container } = render(<AvisoSinResponsable sinTutor={false} />);
    expect(container.textContent?.trim()).toBe('');
  });

  it('no dice nada cuando todavía no se sabe si tiene tutor', () => {
    // null = el backend no consultó el dato (los listados no pagan esa query).
    // Afirmar que falta alguien sin haberlo mirado es peor que callar: manda a
    // asignar un tutor que quizá ya está asignado.
    const { container } = render(<AvisoSinResponsable sinTutor={null} />);
    expect(container.textContent?.trim()).toBe('');
  });
});

describe('AvisoSinResponsable — materia sin nadie a cargo', () => {
  it('avisa cuando la materia no tiene ni profesor ni coordinador', () => {
    render(<AvisoSinResponsable sinResponsableDeMateria nombre="Programación I" />);
    const aviso = screen.getByRole('alert');
    expect(aviso.textContent).toMatch(/profesor/i);
    expect(aviso.textContent).toMatch(/coordinador/i);
  });

  it('no dice nada cuando la materia tiene responsables', () => {
    const { container } = render(
      <AvisoSinResponsable sinResponsableDeMateria={false} sinTutor={false} />,
    );
    expect(container.textContent?.trim()).toBe('');
  });

  it('sin ninguna falta declarada no ocupa lugar en la pantalla', () => {
    const { container } = render(<AvisoSinResponsable />);
    expect(container.textContent?.trim()).toBe('');
  });
});
