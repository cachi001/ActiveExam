import { describe, expect, it } from 'vitest';

import {
  DIAS_VENTANA_POR_DEFECTO,
  MINUTOS_LIMITE_POR_DEFECTO,
  aInputLocal,
  aperturaSugerida,
  cierreSugerido,
  deInputLocalAIso,
  errorDeVentana,
} from './ventanaPorDefecto';

describe('ventana por defecto de un examen nuevo', () => {
  const AHORA = new Date(2026, 8, 1, 14, 30, 45); // 1/9/2026 14:30:45 local

  it('la apertura sugerida es ahora, sin segundos sueltos', () => {
    expect(aperturaSugerida(AHORA)).toBe('2026-09-01T14:30');
  });

  it('el cierre sugerido deja una semana', () => {
    expect(cierreSugerido(AHORA)).toBe('2026-09-08T14:30');
  });

  it('la ventana por defecto coincide con la del backend', () => {
    // Si se desincronizan, el examen creado desde la pantalla y el creado por
    // API quedan con ventanas distintas sin que nadie lo note.
    expect(DIAS_VENTANA_POR_DEFECTO).toBe(7);
  });

  it('usa hora LOCAL, no UTC', () => {
    // `toISOString()` habría devuelto la hora en UTC y el examen abriría
    // corrido varias horas respecto de lo que muestra el formulario.
    expect(aInputLocal(new Date(2026, 0, 5, 9, 5))).toBe('2026-01-05T09:05');
  });

  it('lo que se escribe en el formulario viaja como ISO', () => {
    const iso = deInputLocalAIso('2026-09-01T14:30');
    expect(iso).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    expect(new Date(iso).getFullYear()).toBe(2026);
  });
});

describe('errorDeVentana', () => {
  it('una ventana normal no da error', () => {
    expect(errorDeVentana('2026-09-01T09:00', '2026-09-01T11:00')).toBeNull();
  });

  it('sin fechas avisa que son obligatorias', () => {
    expect(errorDeVentana('', '')).toMatch(/obligatorias/i);
    expect(errorDeVentana('2026-09-01T09:00', '')).toMatch(/obligatorias/i);
  });

  it('rechaza un cierre anterior al inicio', () => {
    expect(errorDeVentana('2026-09-02T09:00', '2026-09-01T09:00')).toMatch(/posterior/i);
  });

  it('rechaza una ventana de duración cero', () => {
    expect(errorDeVentana('2026-09-01T09:00', '2026-09-01T09:00')).toMatch(/posterior/i);
  });

  it('una fecha ilegible no pasa como válida', () => {
    expect(errorDeVentana('no-es-fecha', '2026-09-01T09:00')).toMatch(/no es válida/i);
  });
});

describe('tiempo límite por defecto', () => {
  it('un examen nuevo arranca con una hora', () => {
    expect(MINUTOS_LIMITE_POR_DEFECTO).toBe(60);
  });
});
