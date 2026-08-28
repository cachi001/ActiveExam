/**
 * El campo de fecha se dibuja con el idioma del navegador y no se puede forzar;
 * el texto de al lado es lo único que garantiza que la fecha se lea igual para
 * todos. Ver `fechaArgentina.ts`.
 */
import { describe, expect, it } from 'vitest';
import { fechaEnArgentino } from './fechaArgentina';

describe('fechaEnArgentino', () => {
  it('escribe el mes con letras: 08/09 no puede confundirse con septiembre', () => {
    const texto = fechaEnArgentino('2026-09-08T14:30');
    expect(texto).toContain('8');
    expect(texto).toContain('septiembre');
    expect(texto).toContain('2026');
    expect(texto).toContain('14:30');
  });

  it('usa reloj de 24 horas, no AM/PM', () => {
    const texto = fechaEnArgentino('2026-08-27T22:49');
    expect(texto).toContain('22:49');
    expect(texto.toLowerCase()).not.toContain('pm');
  });

  it('sin valor devuelve vacío, no "Invalid Date"', () => {
    expect(fechaEnArgentino('')).toBe('');
    expect(fechaEnArgentino('cualquier cosa')).toBe('');
  });
});
