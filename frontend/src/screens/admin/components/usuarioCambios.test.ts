/**
 * "Guardar cambios" solo se habilita si HAY cambios.
 *
 * Encontrado probando la pantalla el 26/8/2026: al abrir "Editar usuario" el botón
 * de guardar ya estaba activo sin haber tocado nada. Ofrecer guardar lo que no
 * cambió invita a un PATCH inútil que igual audita, y —peor— borra la señal de si
 * uno modificó algo o no, que es justo lo que se quiere saber antes de confirmar
 * cambios de ROLES sobre una cuenta ajena.
 */
import { describe, it, expect } from 'vitest';
import { hayCambios } from './usuarioCambios';
import type { FormState } from './UsuarioHelpers';
import type { UsuarioAdmin } from '../../../lib/types';

const ORIGINAL = {
  id: 'u-1',
  username: 'tutor1',
  email: 'tutor@activeexam.local',
  nombre: 'Tutor',
  apellido: 'Prueba',
  roles: ['tutor'],
} as unknown as UsuarioAdmin;

const FORM_IGUAL: FormState = {
  email: 'tutor@activeexam.local',
  username: '',
  nombre: 'Tutor',
  apellido: 'Prueba',
  roles: ['tutor'],
};

describe('hayCambios', () => {
  it('recién abierto el formulario, no hay nada que guardar', () => {
    expect(hayCambios(ORIGINAL, FORM_IGUAL)).toBe(false);
  });

  it('detecta un email distinto', () => {
    expect(hayCambios(ORIGINAL, { ...FORM_IGUAL, email: 'otro@activeexam.local' })).toBe(true);
  });

  it('detecta un nombre distinto', () => {
    expect(hayCambios(ORIGINAL, { ...FORM_IGUAL, nombre: 'Tutora' })).toBe(true);
  });

  it('detecta un apellido distinto', () => {
    expect(hayCambios(ORIGINAL, { ...FORM_IGUAL, apellido: 'Otro' })).toBe(true);
  });

  it('detecta que se AGREGÓ un rol', () => {
    expect(hayCambios(ORIGINAL, { ...FORM_IGUAL, roles: ['tutor', 'profesor'] })).toBe(true);
  });

  it('detecta que se QUITÓ un rol', () => {
    expect(hayCambios(ORIGINAL, { ...FORM_IGUAL, roles: [] })).toBe(true);
  });

  it('los mismos roles en otro orden NO son un cambio', () => {
    // Los checkboxes agregan en el orden en que se tocan, así que el mismo
    // conjunto puede llegar en cualquier orden. Compararlo como lista haría que
    // destildar y volver a tildar se viera como una modificación.
    const original = { ...ORIGINAL, roles: ['tutor', 'profesor'] } as UsuarioAdmin;
    expect(hayCambios(original, { ...FORM_IGUAL, roles: ['profesor', 'tutor'] })).toBe(false);
  });

  it('un campo vacío contra uno nulo no es un cambio', () => {
    // El backend devuelve null cuando el usuario no tiene nombre cargado, y el
    // formulario lo representa como "". Tratarlos distinto marcaría como sucio
    // un formulario que nadie tocó.
    const sinNombre = { ...ORIGINAL, nombre: null, apellido: null } as unknown as UsuarioAdmin;
    expect(hayCambios(sinNombre, { ...FORM_IGUAL, nombre: '', apellido: '' })).toBe(false);
  });

  it('sin usuario cargado todavía, no hay cambios que guardar', () => {
    expect(hayCambios(null, FORM_IGUAL)).toBe(false);
  });
});
