import { describe, it, expect } from 'vitest';
import {
  entraACola,
  examInfoDeSesion,
  enriquecerYFiltrar,
  materiasEnRiesgo,
  subtituloExamen,
  SIN_MATERIA,
  SIN_COMISION,
} from './colaAgregacion';
import type { ExamInfo } from './helpers';
import type { SesionProctoringResumen } from '../../lib/types';

const base = (over: Partial<SesionProctoringResumen>): SesionProctoringResumen => ({
  id: 's1',
  modo: 'examen',
  creada_en: '2026-07-08T10:00:00Z',
  total_eventos: 1,
  total_discrepancias: 0,
  score: 100,
  ...over,
});

describe('examInfoDeSesion — prefiere el contexto resuelto server-side', () => {
  it('usa examen_titulo/materia/comisión del backend cuando vienen', () => {
    const info = examInfoDeSesion(
      base({
        examen_contenido_id: 'c-1',
        examen_titulo: 'Programación 1',
        materia_nombre: 'Programación',
        comision_nombre: 'Comisión A',
      }),
    );
    expect(info).not.toBeNull();
    expect(info!.examNombre).toBe('Programación 1');
    expect(info!.materiaNombre).toBe('Programación');
    expect(info!.comisionNombre).toBe('Comisión A');
  });

  it('examen sin comisión/materia asociada: muestra el título pero sentinela en materia/comisión', () => {
    const info = examInfoDeSesion(
      base({ examen_contenido_id: 'c-1', examen_titulo: 'Programación 1' }),
    );
    expect(info!.examNombre).toBe('Programación 1');
    expect(info!.materiaNombre).toBe(SIN_MATERIA);
    expect(info!.comisionNombre).toBe(SIN_COMISION);
  });

  it('sin contexto backend ni exam_id de catálogo → null (cae al mock, que no lo tiene)', () => {
    const info = examInfoDeSesion(base({ exam_id: 'no-existe-en-mock' }));
    expect(info).toBeNull();
  });
});

describe('entraACola — definición canónica de "entra a la Cola de revisión" (c-78 D3)', () => {
  const UMBRAL = 70;

  it('sesión con examen vinculado y score sobre el umbral: entra', () => {
    expect(entraACola(base({ score: 85, examen_contenido_id: 'c-1' }), UMBRAL)).toBe(true);
  });

  it('sesión de diagnóstico (sin examen) sobre el umbral: NO entra', () => {
    // Es el caso que inflaba el contador del Panel de administración: score alto,
    // pero no hay examen ni alumno a quien revisarle nada.
    expect(entraACola(base({ score: 99, examen_contenido_id: null, exam_id: null }), UMBRAL)).toBe(
      false,
    );
  });

  it('sesión con examen vinculado bajo el umbral: NO entra', () => {
    expect(entraACola(base({ score: 40, examen_contenido_id: 'c-1' }), UMBRAL)).toBe(false);
  });

  it('score exactamente en el umbral: entra (el umbral es inclusivo)', () => {
    expect(entraACola(base({ score: UMBRAL, examen_contenido_id: 'c-1' }), UMBRAL)).toBe(true);
  });

  it('sesión del catálogo legacy (exam_id sin examen_contenido_id): entra', () => {
    expect(entraACola(base({ score: 90, exam_id: 'legacy-1' }), UMBRAL)).toBe(true);
  });

  it('ensayo del docente con score alto: NO entra', () => {
    // La Cola de revisión existe para decidir sobre PERSONAS: quien la mira está
    // por juzgar si alguien se copió. Un ensayo del propio docente ahí es ruido
    // que se lee como un caso a revisar, y encima uno que nunca va a tener nota
    // ni veredicto porque las sesiones de prueba no cuentan.
    expect(
      entraACola(base({ score: 99, examen_contenido_id: 'c-1', es_prueba: true }), UMBRAL),
    ).toBe(false);
  });

  it('sesión real (es_prueba false) con score alto: entra', () => {
    expect(
      entraACola(base({ score: 99, examen_contenido_id: 'c-1', es_prueba: false }), UMBRAL),
    ).toBe(true);
  });

  it('es el MISMO criterio que aplica enriquecerYFiltrar (una sola definición)', () => {
    const sesiones = [
      base({ id: 'con-examen', score: 90, examen_contenido_id: 'c-1' }),
      base({ id: 'diagnostico', score: 95 }),
      base({ id: 'bajo-umbral', score: 10, examen_contenido_id: 'c-2' }),
    ];
    const porElPredicado = sesiones.filter((s) => entraACola(s, UMBRAL)).map((s) => s.id);
    const porLaCola = enriquecerYFiltrar(sesiones, UMBRAL).map((i) => i.sesion.id);
    expect(porLaCola).toEqual(porElPredicado);
    expect(porLaCola).toEqual(['con-examen']);
  });
});

describe('enriquecerYFiltrar — el examen importado real ya NO cae en "Sin examen asociado"', () => {
  it('agrupa por el título real del examen resuelto por el backend', () => {
    const sesiones = [
      base({
        id: 's1',
        score: 100,
        examen_contenido_id: 'c-1',
        examen_titulo: 'Programación 1',
        materia_nombre: 'Programación',
        comision_nombre: 'Comisión A',
      }),
    ];
    const items = enriquecerYFiltrar(sesiones, 70);
    expect(items).toHaveLength(1);
    const materias = materiasEnRiesgo(items);
    expect(materias.map((m) => m.nombre)).toEqual(['Programación']);
    expect(materias[0].enRiesgo).toBe(1);
  });

  it('descarta las sesiones bajo el umbral', () => {
    const sesiones = [base({ id: 's1', score: 50, examen_contenido_id: 'c-1', examen_titulo: 'X' })];
    expect(enriquecerYFiltrar(sesiones, 70)).toHaveLength(0);
  });
});

describe('subtituloExamen — subtítulo del header de supervisión en vivo', () => {
  const info = (over: Partial<ExamInfo>): ExamInfo => ({
    examNombre: 'Programación 1',
    materiaNombre: 'Programación',
    comisionNombre: 'Comisión A',
    ...over,
  });

  it('junta materia · comisión', () => {
    expect(subtituloExamen(info({}))).toBe('Programación · Comisión A');
  });

  // c-78: el campo `docente` se sacó de ExamInfo. El backend nunca lo mandó (el
  // propio test anterior lo decía: "contexto server-side no lo trae"), así que
  // quedaba siempre vacío y hacía que tres pantallas de supervisión renderizaran
  // un separador « · » colgando. Si algún día se quiere mostrar al o a los
  // tutores acá, el dato tiene que venir de `comision_tutor` (N:M) y salir del
  // backend en el listado de sesiones — no de un campo que nadie llena.

  it('descarta los sentinelas de materia/comisión sin asignar', () => {
    expect(
      subtituloExamen(info({ materiaNombre: SIN_MATERIA, comisionNombre: SIN_COMISION })),
    ).toBe('');
  });

  it('info null → cadena vacía', () => {
    expect(subtituloExamen(null)).toBe('');
  });
});
