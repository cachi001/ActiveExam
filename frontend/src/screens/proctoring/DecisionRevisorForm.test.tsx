/**
 * Tests — DecisionRevisorForm (c-76 bloque 9.2, D3 del design)
 *
 * D3: "El tutor NUNCA emite veredicto." El boton de veredicto (aprobar/anular)
 * se renderiza SOLO si el usuario tiene `revisar_sesion` (coordinador/revisor/
 * admin); sin esa capacidad, el dossier se ve en modo LECTURA — nada clickeable
 * que dispare una decision (antes "Aprobar con nota" quedaba visible y habilitado
 * incluso sin `puedeResolver`, aunque el backend lo rechazara con 403 — gap de UX
 * que este test cierra).
 *
 * TDD Cycle: RED → GREEN → TRIANGULATE → REFACTOR
 * Framework: vitest + @testing-library/react. Front puro.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import { DecisionRevisorForm } from './DecisionRevisorForm';

afterEach(() => {
  cleanup();
});

describe('DecisionRevisorForm — veredicto solo con revisar_sesion (c-76 bloque 9)', () => {
  it('sin puedeResolver: NO hay boton de veredicto (ni aprobar ni anular)', () => {
    render(
      <DecisionRevisorForm puedeResolver={false} eventos={[]} onResolver={vi.fn()} />,
    );
    expect(screen.queryByRole('button', { name: /aprobar con nota/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /anular examen/i })).toBeNull();
  });

  it('sin puedeResolver: muestra el dossier en modo lectura (aviso explicito)', () => {
    render(
      <DecisionRevisorForm puedeResolver={false} eventos={[]} onResolver={vi.fn()} />,
    );
    expect(screen.getAllByText(/modo lectura/i).length).toBeGreaterThan(0);
  });

  it('con puedeResolver: SI hay boton de aprobar y de anular', () => {
    render(
      <DecisionRevisorForm puedeResolver={true} eventos={[]} onResolver={vi.fn()} />,
    );
    expect(screen.getByRole('button', { name: /aprobar con nota/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /anular examen/i })).toBeTruthy();
  });
});
