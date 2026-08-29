/**
 * AvisoImpactoBaja — el aviso que va DENTRO del diálogo de confirmación de una
 * baja (c-78, Opción C del dueño): dar de baja algo ya rendido se puede, pero
 * quien lo hace tiene que saber cuánta historia hay atrás antes de confirmar.
 *
 * Contrato de presentación puro: recibe el impacto ya consultado y no llama a
 * ningún endpoint. Dos casos distintos y bien separados:
 *   - `sesiones_en_curso > 0` → la baja NO va a poder hacerse (el backend
 *     responde 409). El aviso lo dice como bloqueo, no como advertencia.
 *   - `rendiciones > 0` → la baja sí se puede. Solo informa.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import { AvisoImpactoBaja } from './AvisoImpactoBaja';

const SIN_NADA = {
  sesiones_en_curso: 0,
  rendiciones: 0,
  examenes: 0,
  comisiones: 0,
};

afterEach(() => {
  cleanup();
});

describe('AvisoImpactoBaja', () => {
  it('mientras consulta avisa que está mirando, sin afirmar nada todavía', () => {
    const { container } = render(<AvisoImpactoBaja impacto={null} cargando />);
    expect(container.textContent).toMatch(/revisando/i);
  });

  it('no dice nada cuando no hay ni rendiciones ni gente rindiendo', () => {
    const { container } = render(<AvisoImpactoBaja impacto={SIN_NADA} cargando={false} />);
    expect(container.textContent?.trim()).toBe('');
  });

  it('avisa cuántas rendiciones ya tiene', () => {
    render(
      <AvisoImpactoBaja
        impacto={{ ...SIN_NADA, rendiciones: 42, examenes: 1 }}
        cargando={false}
      />,
    );
    expect(screen.getByText(/42 rendiciones/i)).toBeTruthy();
  });

  it('usa el singular con una sola rendición', () => {
    render(
      <AvisoImpactoBaja
        impacto={{ ...SIN_NADA, rendiciones: 1, examenes: 1 }}
        cargando={false}
      />,
    );
    expect(screen.getByText(/1 rendición\b/i)).toBeTruthy();
  });

  it('con gente rindiendo ahora lo plantea como bloqueo, no como advertencia', () => {
    render(
      <AvisoImpactoBaja
        impacto={{ ...SIN_NADA, sesiones_en_curso: 3, rendiciones: 10, examenes: 1 }}
        cargando={false}
      />,
    );
    const texto = screen.getByRole('alert').textContent ?? '';
    expect(texto).toMatch(/3 alumnos rindiendo/i);
    expect(texto).toMatch(/no se puede dar de baja/i);
  });

  it('cuenta los exámenes y comisiones alcanzados cuando son varios', () => {
    render(
      <AvisoImpactoBaja
        impacto={{ sesiones_en_curso: 0, rendiciones: 5, examenes: 4, comisiones: 2 }}
        cargando={false}
      />,
    );
    const texto = screen.getByRole('note').textContent ?? '';
    expect(texto).toMatch(/2 comisiones/i);
    expect(texto).toMatch(/4 exámenes/i);
  });

  it('no menciona comisiones cuando lo que se da de baja es un examen suelto', () => {
    render(
      <AvisoImpactoBaja
        impacto={{ sesiones_en_curso: 0, rendiciones: 5, examenes: 1, comisiones: 0 }}
        cargando={false}
      />,
    );
    expect(screen.getByRole('note').textContent).not.toMatch(/comisi/i);
  });
});

// ---------------------------------------------------------------------------
// Inscriptos: a cuánta gente le corta el acceso esta baja
// ---------------------------------------------------------------------------
//
// Verificado el 28/8/2026 contra la base de desarrollo: una materia con 4
// alumnos inscriptos se dio de baja y ni la API ni la pantalla los mencionaron.
// Los inscriptos NO bloquean (si bloquearan, una materia con historia no se
// podría retirar nunca), pero quien confirma tiene que saberlo.

describe('AvisoImpactoBaja — inscriptos', () => {
  it('avisa cuántos alumnos inscriptos quedan sin acceso', () => {
    render(
      <AvisoImpactoBaja
        impacto={{ sesiones_en_curso: 0, rendiciones: 0, examenes: 0, comisiones: 1, inscriptos: 4 }}
        cargando={false}
      />,
    );
    expect(screen.getByText(/4 alumnos inscriptos/i)).toBeTruthy();
  });

  it('aclara que la baja se puede hacer igual', () => {
    render(
      <AvisoImpactoBaja
        impacto={{ sesiones_en_curso: 0, rendiciones: 0, examenes: 0, comisiones: 1, inscriptos: 2 }}
        cargando={false}
      />,
    );
    // No puede leerse como un bloqueo: el único bloqueo es gente rindiendo.
    expect(screen.queryByText(/no se puede dar de baja/i)).toBeNull();
  });

  it('sin inscriptos no dice nada', () => {
    const { container } = render(
      <AvisoImpactoBaja
        impacto={{ sesiones_en_curso: 0, rendiciones: 0, examenes: 0, comisiones: 1, inscriptos: 0 }}
        cargando={false}
      />,
    );
    expect(container.textContent).toBe('');
  });

  it('un solo inscripto se escribe en singular', () => {
    render(
      <AvisoImpactoBaja
        impacto={{ sesiones_en_curso: 0, rendiciones: 0, examenes: 0, comisiones: 1, inscriptos: 1 }}
        cargando={false}
      />,
    );
    expect(screen.getByText(/1 alumno inscripto/i)).toBeTruthy();
  });
});
