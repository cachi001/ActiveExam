/**
 * Identidad y búsqueda de la persona en supervisión en vivo.
 *
 * Lo que sostienen estos tests: en el panel del tutor, quién es cada sesión NO
 * puede depender de la etiqueta que mandó el cliente. La etiqueta es un fallback
 * para sesiones viejas; la identidad sale del servidor.
 */
import { describe, expect, it } from 'vitest';
import type { SesionProctoringResumen } from '../../lib/types';
import {
  coincideBusqueda,
  correoPersona,
  inicialDe,
  nombrePersona,
  SIN_IDENTIFICAR,
} from './persona';

function sesion(extra: Partial<SesionProctoringResumen> = {}): SesionProctoringResumen {
  return {
    id: 's-1',
    modo: 'examen',
    creada_en: '2026-09-05T14:00:00.000Z',
    total_eventos: 0,
    total_discrepancias: 0,
    score: 0,
    ...extra,
  } as SesionProctoringResumen;
}

describe('nombrePersona', () => {
  it('usa el nombre que resolvió el servidor', () => {
    expect(
      nombrePersona(sesion({ alumno_nombre: 'Ada Lovelace', etiqueta: 'Parcial 1' })),
    ).toBe('Ada Lovelace');
  });

  it('el nombre del servidor le gana a la etiqueta del cliente', () => {
    // Regla dura #6: el cliente es un sensor no confiable. Si la etiqueta ganara,
    // alguien podría aparecer en el panel del tutor con el nombre de otro.
    expect(
      nombrePersona(sesion({ alumno_nombre: 'Grace Hopper', etiqueta: 'Ada Lovelace' })),
    ).toBe('Grace Hopper');
  });

  it('sin nombre del servidor cae a la etiqueta', () => {
    expect(nombrePersona(sesion({ etiqueta: 'Juan Pérez' }))).toBe('Juan Pérez');
  });

  it('sin nada identificable lo dice, no inventa', () => {
    expect(nombrePersona(sesion({ etiqueta: '   ' }))).toBe(SIN_IDENTIFICAR);
    expect(nombrePersona(sesion())).toBe(SIN_IDENTIFICAR);
  });
});

describe('inicialDe', () => {
  it('toma la inicial del nombre', () => {
    expect(inicialDe(sesion({ alumno_nombre: 'ada lovelace' }))).toBe('A');
  });

  it('sin identificar usa un signo, no una letra al azar', () => {
    expect(inicialDe(sesion())).toBe('?');
  });
});

describe('correoPersona', () => {
  it('devuelve el correo cuando lo hay', () => {
    expect(correoPersona(sesion({ alumno_email: 'ada@uni.edu' }))).toBe('ada@uni.edu');
  });

  it('sin correo devuelve null, y NUNCA el username interno', () => {
    // Un `lti:1:7` en pantalla no le dice nada a nadie y es una clave interna.
    expect(correoPersona(sesion({ alumno_idnumber: 'lti:1:7' }))).toBeNull();
  });
});

describe('coincideBusqueda', () => {
  const ada = sesion({
    alumno_nombre: 'Ada Lovelace',
    alumno_idnumber: '45231',
    alumno_email: 'ada@uni.edu',
    etiqueta: 'Parcial 1',
  });

  it('sin texto, entran todas', () => {
    expect(coincideBusqueda(ada, '')).toBe(true);
    expect(coincideBusqueda(ada, '   ')).toBe(true);
  });

  it('busca por nombre, sin distinguir mayúsculas', () => {
    expect(coincideBusqueda(ada, 'lovelace')).toBe(true);
    expect(coincideBusqueda(ada, 'ADA')).toBe(true);
  });

  it('NO busca por el username interno', () => {
    // `alumno_idnumber` es el username, y para quien entra por el campus vale
    // "lti:1:7". Acá no se maneja legajo: nadie va a tipear eso.
    expect(coincideBusqueda(ada, '45231')).toBe(false);
  });

  it('busca por correo', () => {
    expect(coincideBusqueda(ada, 'ada@uni')).toBe(true);
  });

  it('no matchea lo que no es', () => {
    expect(coincideBusqueda(ada, 'hopper')).toBe(false);
  });

  it('ignora tildes en los dos lados', () => {
    // El docente escribe "perez" con el teclado apurado y la persona es "Pérez".
    const juan = sesion({ alumno_nombre: 'Juan Pérez' });
    expect(coincideBusqueda(juan, 'perez')).toBe(true);
    expect(coincideBusqueda(sesion({ alumno_nombre: 'Juan Perez' }), 'pérez')).toBe(true);
  });

  it('todavía encuentra por la etiqueta a una sesión sin identidad del servidor', () => {
    expect(coincideBusqueda(sesion({ etiqueta: 'Juan Pérez' }), 'juan')).toBe(true);
  });
});
