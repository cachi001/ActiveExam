/**
 * TDD: RED → GREEN → TRIANGULATE — TableToolbar
 *
 * Sin @testing-library/react (no instalado). Usa inspección de fuente
 * (readFileSync) para verificar estructura, props, debounce, paginación
 * y diseño responsivo — el mismo patrón que QuestionNavigator.test.tsx.
 */

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, 'TableToolbar.tsx'), 'utf8');

// ---------------------------------------------------------------------------
// 1. RED — Tipos exportados
// ---------------------------------------------------------------------------

describe('1.1 TableToolbar — tipos exportados', () => {
  it('exporta la interfaz TableQuery', () => {
    expect(src).toMatch(/export\s+interface\s+TableQuery/);
  });

  it('TableQuery tiene los campos q, filters, page, page_size', () => {
    expect(src).toMatch(/q\s*:/);
    expect(src).toMatch(/filters\s*:/);
    expect(src).toMatch(/page\s*:/);
    expect(src).toMatch(/page_size\s*:/);
  });

  it('exporta la interfaz FilterDef', () => {
    expect(src).toMatch(/export\s+interface\s+FilterDef/);
  });

  it('FilterDef tiene key, label y options[]', () => {
    expect(src).toMatch(/key\s*:/);
    expect(src).toMatch(/label\s*:/);
    expect(src).toMatch(/options\s*:/);
  });

  it('exporta TableToolbarProps', () => {
    expect(src).toMatch(/export\s+interface\s+TableToolbarProps/);
  });
});

// ---------------------------------------------------------------------------
// 2. RED → GREEN — Exportación del componente y props mínimas
// ---------------------------------------------------------------------------

describe('2.1 TableToolbar — exportación y props', () => {
  it('exporta TableToolbar como named export', () => {
    expect(src).toMatch(/export\s+function\s+TableToolbar/);
  });

  it('acepta la prop query (TableQuery)', () => {
    expect(src).toMatch(/query\s*:/);
  });

  it('acepta la prop onChange (callback)', () => {
    expect(src).toMatch(/onChange\s*:/);
  });

  it('acepta filterDefs (opcional)', () => {
    expect(src).toMatch(/filterDefs/);
  });

  it('acepta total (opcional, para paginación)', () => {
    expect(src).toMatch(/total/);
  });

  it('acepta pageSizeOptions (opcional)', () => {
    expect(src).toMatch(/pageSizeOptions/);
  });

  it('acepta loading (opcional)', () => {
    expect(src).toMatch(/loading/);
  });
});

// ---------------------------------------------------------------------------
// 3. GREEN — Debounce de búsqueda
// ---------------------------------------------------------------------------

describe('3.1 TableToolbar — debounce de búsqueda', () => {
  it('usa setTimeout con 300ms para el debounce', () => {
    expect(src).toMatch(/setTimeout/);
    expect(src).toMatch(/300/);
  });

  it('cancela el timeout anterior con clearTimeout al escribir', () => {
    expect(src).toMatch(/clearTimeout/);
  });

  it('guarda la referencia del timeout en useRef para limpiarlo', () => {
    expect(src).toMatch(/debounceRef/);
    expect(src).toMatch(/useRef/);
  });

  it('resetea page a 1 al emitir cambio de búsqueda', () => {
    // el onChange con debounce siempre emite page: 1
    expect(src).toMatch(/page\s*:\s*1/);
  });

  it('mantiene estado interno internalQ separado del prop query.q', () => {
    expect(src).toMatch(/internalQ/);
    expect(src).toMatch(/setInternalQ/);
  });
});

// ---------------------------------------------------------------------------
// 4. GREEN — Filtros declarativos
// ---------------------------------------------------------------------------

describe('4.1 TableToolbar — filtros declarativos (selects)', () => {
  it('renderiza un <select> por cada FilterDef usando .map()', () => {
    expect(src).toMatch(/filterDefs\.map/);
    expect(src).toMatch(/<select/);
  });

  it('usa fd.key como key del elemento mapeado', () => {
    expect(src).toMatch(/key=\{fd\.key\}/);
  });

  it('llama handleFilterChange al cambiar un select', () => {
    expect(src).toMatch(/handleFilterChange/);
  });

  it('resetea page a 1 cuando cambia un filtro', () => {
    // handleFilterChange emite page: 1
    expect(src).toMatch(/page\s*:\s*1/);
  });

  it('muestra las options del FilterDef', () => {
    expect(src).toMatch(/fd\.options\.map/);
    expect(src).toMatch(/<option/);
  });
});

// ---------------------------------------------------------------------------
// 5. TRIANGULATE — Paginación
// ---------------------------------------------------------------------------

describe('5.1 TableToolbar — controles de paginación', () => {
  it('muestra la paginación solo cuando total está definido', () => {
    // Renderiza el bloque de paginación condicionalmente
    expect(src).toMatch(/total\s*!==\s*undefined/);
  });

  it('renderiza botón de página anterior', () => {
    expect(src).toMatch(/Página anterior/);
  });

  it('renderiza botón de página siguiente', () => {
    expect(src).toMatch(/Página siguiente/);
  });

  it('deshabilita "anterior" cuando está en la primera página', () => {
    expect(src).toMatch(/canPrev/);
  });

  it('deshabilita "siguiente" cuando no hay más páginas', () => {
    expect(src).toMatch(/canNext/);
  });

  it('calcula totalPages correctamente (ceil)', () => {
    expect(src).toMatch(/Math\.ceil/);
    expect(src).toMatch(/totalPages/);
  });

  it('tiene selector de page_size', () => {
    expect(src).toMatch(/handlePageSizeChange/);
    expect(src).toMatch(/pageSizeOptions\.map/);
  });

  it('muestra info de ítems (rango de / total)', () => {
    // Muestra "X–Y de Z"
    expect(src).toMatch(/de \$\{total\}/);
  });
});

// ---------------------------------------------------------------------------
// 6. TRIANGULATE — Diseño responsivo y UX
// ---------------------------------------------------------------------------

describe('6.1 TableToolbar — responsive y UX', () => {
  it('apila el toolbar verticalmente en mobile (flex-col) y horizontal en sm (flex-row)', () => {
    expect(src).toMatch(/flex-col\s+sm:flex-row/);
  });

  it('tiene botón de limpiar búsqueda (clear)', () => {
    expect(src).toMatch(/Limpiar búsqueda/);
  });

  it('muestra un spinner de carga cuando loading=true', () => {
    expect(src).toMatch(/ae-spin/);
    expect(src).toMatch(/progress_activity/);
  });

  it('deshabilita el input de búsqueda mientras carga', () => {
    expect(src).toMatch(/disabled=\{loading\}/);
  });

  it('el input tiene aria-label para accesibilidad', () => {
    expect(src).toMatch(/aria-label=\{placeholder\}/);
  });

  it('usa chevron_left / chevron_right para los botones de paginación', () => {
    expect(src).toMatch(/chevron_left/);
    expect(src).toMatch(/chevron_right/);
  });
});

// ---------------------------------------------------------------------------
// 7. REFACTOR — Convenciones del proyecto
// ---------------------------------------------------------------------------

describe('7.1 TableToolbar — convenciones', () => {
  it('no importa @testing-library', () => {
    expect(src).not.toMatch(/@testing-library/);
  });

  it('no usa filtrado en memoria (client-side)', () => {
    // NO debe tener Array.filter sobre items
    expect(src).not.toMatch(/\.filter\s*\(\s*\(.*\)\s*=>/);
  });

  it('usa tokens del design system (border-outline-variant, text-on-surface)', () => {
    expect(src).toMatch(/border-outline-variant/);
    expect(src).toMatch(/text-on-surface/);
  });

  it('usa Icon del design system', () => {
    expect(src).toMatch(/from '\.\/components'/);
    expect(src).toMatch(/Icon/);
  });
});
