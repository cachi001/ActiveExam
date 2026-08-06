import { describe, it, expect } from 'vitest';
import {
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
    docente: 'Ing. Romero',
    ...over,
  });

  it('junta materia · comisión · docente cuando están todos', () => {
    expect(subtituloExamen(info({}))).toBe('Programación · Comisión A · Ing. Romero');
  });

  it('omite el tutor vacío (contexto server-side no lo trae)', () => {
    expect(subtituloExamen(info({ docente: '' }))).toBe('Programación · Comisión A');
  });

  it('descarta los sentinelas de materia/comisión sin asignar', () => {
    expect(
      subtituloExamen(info({ materiaNombre: SIN_MATERIA, comisionNombre: SIN_COMISION, docente: '' })),
    ).toBe('');
  });

  it('info null → cadena vacía', () => {
    expect(subtituloExamen(null)).toBe('');
  });
});
