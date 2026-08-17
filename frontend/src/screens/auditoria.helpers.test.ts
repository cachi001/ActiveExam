import { describe, expect, it } from 'vitest';
import { configDiff, labelConfig } from './auditoria.helpers';

describe('configDiff', () => {
  it('propósito plano (no JSON) → null (se muestra tal cual)', () => {
    expect(configDiff('Creó la materia Álgebra I (ALG101)')).toBeNull();
    expect(configDiff(null)).toBeNull();
    expect(configDiff('')).toBeNull();
  });

  it('JSON sin forma {before, after} → null', () => {
    expect(configDiff('{"foo": 1}')).toBeNull();
  });

  it('diffea solo los parámetros que cambiaron (ignora los iguales y `version`)', () => {
    const proposito = JSON.stringify({
      before: { version: 1, chat_habilitado: true, pausa_max_min: 10, umbral_cola_revision: 70 },
      after: { version: 2, chat_habilitado: false, pausa_max_min: 10, umbral_cola_revision: 70 },
    });
    const diff = configDiff(proposito);
    expect(diff).toHaveLength(1);
    expect(diff![0]).toMatchObject({
      key: 'chat_habilitado',
      label: 'Chat tutor–alumno',
      antes: 'Sí',
      despues: 'No',
    });
  });

  it('formatea arrays como "N ítems" y detecta el cambio', () => {
    const proposito = JSON.stringify({
      before: { detectores_activos: ['a', 'b', 'c'] },
      after: { detectores_activos: ['a', 'b'] },
    });
    const diff = configDiff(proposito);
    expect(diff).toHaveLength(1);
    expect(diff![0]).toMatchObject({ antes: '3 ítems', despues: '2 ítems' });
  });

  it('sin cambios efectivos → lista vacía (no null)', () => {
    const proposito = JSON.stringify({ before: { chat_habilitado: true }, after: { chat_habilitado: true } });
    expect(configDiff(proposito)).toEqual([]);
  });
});

describe('labelConfig', () => {
  it('mapea claves conocidas y prettifica las desconocidas', () => {
    expect(labelConfig('umbral_cola_revision')).toBe('Umbral de revisión');
    expect(labelConfig('algo_nuevo_raro')).toBe('algo nuevo raro');
  });
});
