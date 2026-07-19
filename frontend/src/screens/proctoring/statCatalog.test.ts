import { describe, expect, it } from 'vitest';
import { STAT_META, statProps } from './statCatalog';

// C-72 sección 11: fuente ÚNICA de vocabulario de las statcards. Métricas
// equivalentes (eventos, discrepancias, riesgo, sesiones) deben usar el MISMO
// label / icono / tono en todas las pantallas. La `sub` (descripción) puede
// contextualizarse por pantalla vía override, pero NUNCA el label/icono/tono.

describe('statCatalog — vocabulario canónico (C-72 sección 11)', () => {
  it('mismo key → mismo label/icono/tono, sin importar el valor', () => {
    const a = statProps('eventos', 5);
    const b = statProps('eventos', 999);
    expect(a.label).toBe(b.label);
    expect(a.icon).toBe(b.icon);
    expect(a.tono).toBe(b.tono);
  });

  it('usa la descripción por defecto del catálogo cuando no hay override', () => {
    expect(statProps('eventos', 5).sub).toBe(STAT_META.eventos.defaultSub);
  });

  it('un override de sub NO altera label/icono/tono (solo contextualiza)', () => {
    const canon = statProps('discrepancias', 3);
    const conScope = statProps('discrepancias', 3, 'en la sesión');
    expect(conScope.sub).toBe('en la sesión');
    expect(conScope.label).toBe(canon.label);
    expect(conScope.icon).toBe(canon.icon);
    expect(conScope.tono).toBe(canon.tono);
  });

  it('la métrica Sesiones NO usa un icono de video (RN-CC: no hay grabación)', () => {
    // El icono viejo `video_library` sugería grabación — engañoso, no hay video.
    expect(STAT_META.sesiones.icon).not.toBe('video_library');
  });

  it('pasa el value a través tal cual', () => {
    expect(statProps('riesgoAlto', 7).value).toBe(7);
  });
});
