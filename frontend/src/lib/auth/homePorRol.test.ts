/**
 * A dónde entra cada rol al sistema.
 *
 * ## Los dos bugs que esto cierra, encontrados probando producción el 26/8/2026
 *
 * **1. El TUTOR no podía entrar.** `homePorRol` lo mandaba a `/admin/examenes`, que
 * exige la capacidad de crear exámenes — algo que el tutor perdió en c-78. El
 * resultado: entraba con su clave, la app lo llevaba a esa ruta y le mostraba "Sin
 * permisos". El tutor es quien devuelve las notas al campus; dejarlo afuera del
 * sistema a días del parcial es bloqueante.
 *
 * **2. "Volver al inicio" no volvía a ningún lado.** La pantalla de "Sin permisos"
 * navegaba a `/login`, pero el usuario YA estaba autenticado, así que el login lo
 * rebotaba a su home... que era la misma ruta sin permiso. Bucle cerrado, sin salida
 * salvo cerrar sesión.
 *
 * ## Por qué esta función vive acá y no dentro de Login.tsx
 *
 * Estaba privada en `Login.tsx` y **duplicada a mano en su propio test**, con un
 * comentario que reconocía la copia. Las dos versiones ya habían divergido: la real
 * mandaba al tutor a `/admin/examenes`, la del test ni contemplaba al tutor. Un test
 * que valida una copia de la función no prueba nada sobre la que corre en producción.
 */
import { describe, it, expect } from 'vitest';
import { homePorRol } from './homePorRol';

describe('homePorRol', () => {
  it('el tutor NO entra a una ruta que no puede ver', () => {
    // El bug exacto: /admin/examenes exige CREAR_EXAMENES, que el tutor no tiene.
    expect(homePorRol(['tutor'])).not.toBe('/admin/examenes');
  });

  it('el tutor entra al panel académico, que sí le corresponde', () => {
    expect(homePorRol(['tutor'])).toBe('/admin');
  });

  it('admin_sistema entra al panel', () => {
    expect(homePorRol(['admin_sistema'])).toBe('/admin');
  });

  it('coordinador entra al panel', () => {
    expect(homePorRol(['coordinador'])).toBe('/admin');
  });

  it('profesor entra al panel', () => {
    // c-78 sumó el rol y homePorRol nunca lo contempló: caía al portal del alumno.
    expect(homePorRol(['profesor'])).toBe('/admin');
  });

  it('el estudiante entra a su portal', () => {
    expect(homePorRol(['estudiante'])).toBe('/alumno');
  });

  it('sin roles cae al portal del alumno', () => {
    // El default más restrictivo: es el área que no exige ninguna capacidad.
    expect(homePorRol([])).toBe('/alumno');
  });

  it('admin_sistema le gana a estudiante cuando hay varios roles', () => {
    expect(homePorRol(['estudiante', 'admin_sistema'])).toBe('/admin');
  });

  it('cualquier rol de staff manda sobre estudiante', () => {
    expect(homePorRol(['estudiante', 'tutor'])).toBe('/admin');
  });
});
