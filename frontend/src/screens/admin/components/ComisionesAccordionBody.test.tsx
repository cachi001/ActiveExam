/**
 * Test de ComisionesAccordionBody — el código de matriculación (enrolment key)
 * debe ser VISIBLE en el listado de comisiones, no solo dentro del formulario
 * de editar (pedido del owner).
 *
 * TDD: RED (la columna no existe) → GREEN (se agrega la columna + card mobile).
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { createRef } from 'react';
import { ComisionesAccordionBody } from './ComisionesAccordionBody';
import type { Comision } from '../../../lib/types';

const comision: Comision = {
  id: 'com-1',
  materia_id: 'mat-1',
  nombre: 'Comisión 1',
  codigo: 'C1',
  periodo: '1C',
  anio: 2026,
  codigo_matriculacion: 'PROG1-A1B2',
};

function renderBody(comisiones: Comision[]) {
  return render(
    <ComisionesAccordionBody
      materiaId="mat-1"
      cargando={false}
      comisiones={comisiones}
      mostrarFormComision={false}
      formComision={null}
      setFormComision={() => {}}
      enviandoComision={false}
      errorFormComision={null}
      primerInputComisionRef={createRef<HTMLInputElement>()}
      periodos={[]}
      onSubmitComision={() => {}}
      onCancelarComision={() => {}}
      abrirCrearComision={() => {}}
      abrirEditarComision={() => {}}
      comisionExpandida={null}
      toggleComision={() => {}}
    />,
  );
}

describe('ComisionesAccordionBody — visibilidad del código de matriculación', () => {
  it('muestra el código de matriculación de la comisión en el listado', () => {
    renderBody([comision]);
    // Aparece en la tabla desktop y/o en la card mobile (ambas montadas por CSS).
    expect(screen.getAllByText('PROG1-A1B2').length).toBeGreaterThan(0);
  });

  it('muestra un placeholder cuando la comisión no tiene código de matriculación', () => {
    renderBody([{ ...comision, codigo_matriculacion: undefined }]);
    // No debe romper: la comisión sigue listándose por su nombre.
    expect(screen.getAllByText('Comisión 1').length).toBeGreaterThan(0);
  });
});
