/**
 * El examen sorteado no se puede pedir antes de que exista la sesión.
 *
 * ## El defecto (reportado el 29/8/2026: "el examen me apareció con 0 preguntas")
 *
 * En `modo_preguntas = 'sorteo_por_intento'` las preguntas se sortean en el
 * PRIMER `GET /exam-content/{id}`, y ese sorteo necesita una sesión de proctoring
 * abierta del alumno: el backend busca la sesión y, si no la encuentra, devuelve
 * `preguntas: []` sin sortear nada (ver `taking_router`, "si sesion is not None").
 *
 * El efecto que carga las preguntas en `Examen.tsx` dependía SOLO de
 * `examen.examen_contenido_id`, así que salía en paralelo con la creación de la
 * sesión (`useExamProctoring`). Si el fetch ganaba la carrera, el alumno recibía
 * un examen VACÍO — y no se recuperaba solo, porque el efecto no volvía a correr.
 *
 * Verificado en la base: la sesión del dueño quedó con `examen_iniciado_en` NULL
 * y 0 filas en `pregunta_sesion`; al repetir el GET con la sesión ya creada,
 * sorteó las 5 correctamente.
 *
 * Que además no se pueda entregar es la consecuencia: sin preguntas no hay qué
 * enviar.
 *
 * ## Qué fija este test
 *
 * `puedeCargarPreguntas` es la guarda del efecto. Se extrajo para poder probar la
 * condición sin montar `Examen` entero (cámara, MediaPipe, store, router).
 */

import { describe, expect, it } from 'vitest';

import {
  MAX_REINTENTOS_CARGA,
  debeReintentarCarga,
  puedeCargarPreguntas,
} from './Examen.cargaDePreguntas';

describe('carga de preguntas del examen', () => {
  it('no pide el examen si todavía no hay sesión', () => {
    // Es el bug: sin sesión el backend no sortea y devuelve 0 preguntas.
    expect(puedeCargarPreguntas('examen-1', null)).toBe(false);
  });

  it('pide el examen cuando la sesión ya existe', () => {
    expect(puedeCargarPreguntas('examen-1', 'sesion-1')).toBe(true);
  });

  it('sin examen no pide nada, aunque haya sesión', () => {
    expect(puedeCargarPreguntas(undefined, 'sesion-1')).toBe(false);
    expect(puedeCargarPreguntas('', 'sesion-1')).toBe(false);
  });

  it('sin examen ni sesión tampoco', () => {
    expect(puedeCargarPreguntas(undefined, null)).toBe(false);
  });
});

describe('reintento cuando el examen llega vacío', () => {
  it('reintenta si llegó sin preguntas', () => {
    expect(debeReintentarCarga(0, 0, true)).toBe(true);
  });

  it('no reintenta si ya trajo preguntas', () => {
    expect(debeReintentarCarga(5, 0, true)).toBe(false);
  });

  it('corta después de unos intentos: no deja un bucle golpeando la API', () => {
    expect(debeReintentarCarga(0, MAX_REINTENTOS_CARGA, true)).toBe(false);
  });

  it('no reintenta si todavía falta la sesión: primero hay que tenerla', () => {
    expect(debeReintentarCarga(0, 0, false)).toBe(false);
  });
});
