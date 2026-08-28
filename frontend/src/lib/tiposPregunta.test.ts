/**
 * Las etiquetas de tipo estaban copiadas en tres pantallas y ninguna cubría
 * `multiple_choice`, que es lo que el banco guarda de verdad: el selector de
 * sorteo mostraba "multiple_choice (8)" al docente.
 */
import { describe, expect, it } from 'vitest';
import { etiquetaDeTipo } from './tiposPregunta';

describe('etiquetaDeTipo', () => {
  it('traduce la grafía que usa el banco', () => {
    expect(etiquetaDeTipo('multiple_choice')).toBe('Opción múltiple');
  });

  it('traduce también la grafía de Moodle, que llega en los imports', () => {
    expect(etiquetaDeTipo('multichoice')).toBe('Opción múltiple');
  });

  it('un tipo que no conoce se muestra tal cual, no vacío', () => {
    // Preferible leer "essay" a leer un renglón en blanco.
    expect(etiquetaDeTipo('essay')).toBe('essay');
  });
});
