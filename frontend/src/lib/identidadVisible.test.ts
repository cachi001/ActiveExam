/**
 * c-78 — la clave interna del provisioning LTI nunca se dibuja.
 *
 * El bug que cierra: el alumno entraba desde Moodle, creaba su usuario y
 * contraseña, y al abrir el Perfil veía `lti:1:7` como su nombre de usuario.
 */
import { describe, it, expect } from 'vitest';
import {
  USUARIO_SIN_COMPLETAR,
  esUsernameSintetico,
  nombreVisible,
  usernameAdmin,
  usernameVisible,
} from './identidadVisible';

describe('esUsernameSintetico', () => {
  it('reconoce el username que genera el provisioning LTI', () => {
    expect(esUsernameSintetico('lti:1:7')).toBe(true);
    expect(esUsernameSintetico('lti:99:1234')).toBe(true);
  });

  it('no confunde un username elegido por la persona', () => {
    expect(esUsernameSintetico('juana.perez')).toBe(false);
    expect(esUsernameSintetico('EST-001')).toBe(false);
    // Contiene "lti" pero no arranca con el prefijo: es un nombre legítimo.
    expect(esUsernameSintetico('multi:algo')).toBe(false);
    expect(esUsernameSintetico('altificado')).toBe(false);
  });

  it('es case-insensitive (equivocarse acá significa mostrar la clave igual)', () => {
    expect(esUsernameSintetico('LTI:1:7')).toBe(true);
    expect(esUsernameSintetico('  Lti:1:7  ')).toBe(true);
  });

  it('vacío o ausente no es sintético', () => {
    expect(esUsernameSintetico('')).toBe(false);
    expect(esUsernameSintetico(null)).toBe(false);
    expect(esUsernameSintetico(undefined)).toBe(false);
  });
});

describe('usernameVisible — qué se muestra en el campo "Usuario"', () => {
  it('muestra el username que la persona eligió', () => {
    expect(usernameVisible('juana.perez', 'juana@uni.edu')).toBe('juana.perez');
  });

  it('con el sintético dice "Sin completar", haya email o no', () => {
    expect(usernameVisible('lti:1:7', 'juana@uni.edu')).toBe(USUARIO_SIN_COMPLETAR);
    expect(usernameVisible('lti:1:7', null)).toBe(USUARIO_SIN_COMPLETAR);
    expect(usernameVisible('lti:1:7')).toBe(USUARIO_SIN_COMPLETAR);
  });

  it('sin username muestra el email', () => {
    expect(usernameVisible(null, 'juana@uni.edu')).toBe('juana@uni.edu');
  });

  it('sin nada muestra el guion (no afirma nada)', () => {
    expect(usernameVisible(null, null)).toBe('—');
  });
});

describe('nombreVisible — cómo se llama la persona', () => {
  it('prefiere nombre y apellido', () => {
    expect(
      nombreVisible({ nombre: 'Juana', apellido: 'Pérez', username: 'lti:1:7' }),
    ).toBe('Juana Pérez');
  });

  it('con solo nombre lo usa', () => {
    expect(nombreVisible({ nombre: 'Juana', username: 'lti:1:7' })).toBe('Juana');
  });

  it('sin nombre cae al username elegido', () => {
    expect(nombreVisible({ username: 'juana.perez' })).toBe('juana.perez');
  });

  it('sin nombre y con sintético dice "Sin completar", no el email', () => {
    expect(nombreVisible({ username: 'lti:1:7', email: 'juana@uni.edu' })).toBe(
      USUARIO_SIN_COMPLETAR,
    );
  });

  it('sin nada útil dice "Sin completar", el mismo texto de siempre', () => {
    expect(nombreVisible({ username: 'lti:1:7' })).toBe(USUARIO_SIN_COMPLETAR);
  });
});

describe('usernameAdmin — qué ve el admin en Usuarios y Detalle de usuario', () => {
  it('con el sintético dice el ESTADO, no la clave interna', () => {
    const r = usernameAdmin('lti:1:7');
    expect(r.texto).not.toContain('lti');
    expect(r.texto).toBe(USUARIO_SIN_COMPLETAR);
    expect(r.pendiente).toBe(true);
  });

  it('dice lo MISMO que ve el alumno: un solo texto en todo el sistema', () => {
    expect(usernameAdmin('lti:1:7').texto).toBe(usernameVisible('lti:1:7'));
    expect(usernameAdmin('lti:1:7').texto).toBe(
      usernameVisible('lti:1:7', 'juana@uni.edu'),
    );
  });

  it('con un username elegido lo muestra tal cual', () => {
    const r = usernameAdmin('juana.perez');
    expect(r.texto).toBe('juana.perez');
    expect(r.pendiente).toBe(false);
  });

  it('sin username muestra el guion, no vacío', () => {
    expect(usernameAdmin(null)).toEqual({ texto: '—', pendiente: false });
    expect(usernameAdmin('')).toEqual({ texto: '—', pendiente: false });
  });
});
