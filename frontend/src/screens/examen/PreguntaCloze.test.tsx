/**
 * Test de PreguntaCloze — blanks tipo "matching" (C-78, emparejamiento).
 * matching se normaliza a cloze en el backend (moodle_parser.py); acá se
 * verifica que el frontend lo renderiza como <select> (igual que multichoice),
 * NO como <input type="text"> libre (que es lo que pasaba antes del fix, ya
 * que "matching" no estaba en la lista de tipos que cuentan como multichoice).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { PreguntaCloze } from './PreguntaCloze';
import type { BlankRendicion } from '../../lib/examTakingApi';

afterEach(cleanup);

const BLANK_MATCHING: BlankRendicion = {
  id: 'b1',
  orden: 0,
  tipo: 'matching',
  texto_antes: 'Python:  ',
  texto_despues: '',
  opciones: [
    { id: 'o1', texto: 'Multiparadigma', orden: 0 },
    { id: 'o2', texto: 'Funcional', orden: 1 },
  ],
};

const BLANK_SHORTANSWER: BlankRendicion = {
  id: 'b2',
  orden: 0,
  tipo: 'shortanswer',
  texto_antes: '¿Como se llama la funcion?\n\n',
  texto_despues: '',
  opciones: [],
};

describe('PreguntaCloze — blank tipo matching', () => {
  it('renderiza un <select> (no un input de texto libre) para un blank matching', () => {
    render(<PreguntaCloze blanks={[BLANK_MATCHING]} respuestas={{}} onRespuesta={() => {}} />);
    expect(screen.getByRole('combobox')).not.toBeNull();
    expect(screen.queryByPlaceholderText('Respuesta')).toBeNull();
  });

  it('el <select> lista todas las opciones del pool', () => {
    render(<PreguntaCloze blanks={[BLANK_MATCHING]} respuestas={{}} onRespuesta={() => {}} />);
    expect(screen.getByText('Multiparadigma')).not.toBeNull();
    expect(screen.getByText('Funcional')).not.toBeNull();
  });

  it('al elegir una opción, llama onRespuesta con el blankId y el id de la opción', () => {
    const onRespuesta = vi.fn();
    render(<PreguntaCloze blanks={[BLANK_MATCHING]} respuestas={{}} onRespuesta={onRespuesta} />);
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    select.value = 'o2';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    expect(onRespuesta).toHaveBeenCalledWith('b1', 'o2');
  });

  it('un blank shortanswer sigue renderizando un input de texto libre (sin cambios)', () => {
    render(<PreguntaCloze blanks={[BLANK_SHORTANSWER]} respuestas={{}} onRespuesta={() => {}} />);
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.getByPlaceholderText('Respuesta')).not.toBeNull();
  });
});
