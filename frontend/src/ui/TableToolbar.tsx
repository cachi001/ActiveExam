/**
 * TableToolbar — toolbar de filtros serverside genérico y reutilizable.
 *
 * Uso:
 *   const [query, setQuery] = useState<TableQuery>({ q: '', filters: {}, page: 1, page_size: 25 });
 *   <TableToolbar query={query} onChange={setQuery} placeholder="Buscar…" filterDefs={[...]} total={100} />
 *
 * Quien lo usa dispara el fetch serverside con los nuevos params en onChange.
 * NO filtra en memoria.
 *
 * Responsive: en mobile (~390px) el toolbar se apila verticalmente.
 */

import { useEffect, useRef, useState } from 'react';
import { Icon } from './components';

// ---------------------------------------------------------------------------
// Tipos públicos (reutilizables en cualquier pantalla)
// ---------------------------------------------------------------------------

/** Estado de query que TableToolbar emite y quien lo usa pasa al backend. */
export interface TableQuery {
  q: string;
  filters: Record<string, string>;
  page: number;
  page_size: number;
}

/** Definición declarativa de un filtro select. */
export interface FilterDef {
  key: string;
  label: string;
  placeholder?: string;
  options: { value: string; label: string }[];
}

export interface TableToolbarProps {
  query: TableQuery;
  onChange: (next: TableQuery) => void;
  placeholder?: string;
  filterDefs?: FilterDef[];
  /** Total de ítems para calcular paginación. Undefined = no muestra paginación. */
  total?: number;
  pageSizeOptions?: number[];
  loading?: boolean;
}

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------

export function TableToolbar({
  query,
  onChange,
  placeholder = 'Buscar…',
  filterDefs = [],
  total,
  pageSizeOptions = [10, 25, 50],
  loading = false,
}: TableToolbarProps) {
  const [internalQ, setInternalQ] = useState(query.q);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track the last q we emitted so external sync doesn't re-trigger the debounce.
  const lastEmittedQ = useRef(query.q);

  // Sync external q → internal (e.g. when caller resets filters)
  useEffect(() => {
    if (query.q !== lastEmittedQ.current) {
      setInternalQ(query.q);
      lastEmittedQ.current = query.q;
    }
  }, [query.q]);

  function handleQChange(value: string) {
    setInternalQ(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      lastEmittedQ.current = value;
      onChange({ ...query, q: value, page: 1 });
    }, 300);
  }

  function handleFilterChange(key: string, value: string) {
    onChange({ ...query, filters: { ...query.filters, [key]: value }, page: 1 });
  }

  function handlePageChange(page: number) {
    onChange({ ...query, page });
  }

  function handlePageSizeChange(ps: number) {
    onChange({ ...query, page_size: ps, page: 1 });
  }

  const totalPages = total !== undefined ? Math.max(1, Math.ceil(total / query.page_size)) : undefined;
  const canPrev = query.page > 1;
  const canNext = totalPages !== undefined ? query.page < totalPages : false;

  return (
    <div className="space-y-sm">
      {/* Search + filters row */}
      <div className="flex flex-col sm:flex-row gap-sm">
        {/* Search input */}
        <div className="flex-1 flex items-center gap-base bg-white border border-outline-variant rounded-xl px-sm py-2
          focus-within:border-primary transition-colors min-w-0">
          <Icon name="search" className="text-on-surface-variant text-[20px] shrink-0" />
          <input
            type="text"
            value={internalQ}
            onChange={(e) => handleQChange(e.target.value)}
            placeholder={placeholder}
            disabled={loading}
            aria-label={placeholder}
            className="flex-1 bg-transparent outline-none text-label-md text-on-surface placeholder:text-on-surface-variant/60 min-w-0"
          />
          {internalQ && !loading && (
            <button
              type="button"
              onClick={() => handleQChange('')}
              aria-label="Limpiar búsqueda"
              className="text-on-surface-variant hover:text-on-surface transition-colors shrink-0"
            >
              <Icon name="close" className="text-[18px]" />
            </button>
          )}
          {loading && (
            <Icon name="progress_activity" className="ae-spin text-primary text-[18px] shrink-0" />
          )}
        </div>

        {/* Declarative select filters */}
        {filterDefs.map((fd) => (
          <select
            key={fd.key}
            value={query.filters[fd.key] ?? ''}
            onChange={(e) => handleFilterChange(fd.key, e.target.value)}
            disabled={loading}
            aria-label={fd.label}
            className="bg-white border border-outline-variant rounded-xl px-sm py-2 text-label-md text-on-surface
              focus:outline-none focus:border-primary transition-colors cursor-pointer
              disabled:opacity-50 disabled:cursor-not-allowed sm:w-auto w-full"
          >
            <option value="">{fd.placeholder ?? `Todos (${fd.label})`}</option>
            {fd.options.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        ))}
      </div>

      {/* Pagination row (only when total is known) */}
      {total !== undefined && (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-sm text-label-sm text-on-surface-variant">
          {/* Left: item count info */}
          <span>
            {total === 0
              ? 'Sin resultados'
              : `${Math.min((query.page - 1) * query.page_size + 1, total)}–${Math.min(query.page * query.page_size, total)} de ${total}`}
          </span>

          {/* Right: controls */}
          <div className="flex items-center gap-sm">
            {/* Page size selector */}
            <div className="flex items-center gap-base">
              <span className="text-on-surface-variant">Por página:</span>
              <select
                value={query.page_size}
                onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                disabled={loading}
                aria-label="Ítems por página"
                className="bg-white border border-outline-variant rounded-md px-xs py-base text-label-sm
                  focus:outline-none focus:border-primary transition-colors cursor-pointer
                  disabled:opacity-50"
              >
                {pageSizeOptions.map((ps) => (
                  <option key={ps} value={ps}>{ps}</option>
                ))}
              </select>
            </div>

            {/* Prev / page info / Next */}
            <div className="flex items-center gap-xs">
              <button
                type="button"
                onClick={() => handlePageChange(query.page - 1)}
                disabled={!canPrev || loading}
                aria-label="Página anterior"
                className="inline-flex items-center justify-center w-8 h-8 rounded-md
                  text-on-surface-variant hover:bg-surface-container hover:text-on-surface
                  disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Icon name="chevron_left" className="text-[20px]" />
              </button>

              <span className="tabular-nums text-on-surface font-medium px-xs">
                {query.page}{totalPages !== undefined ? ` / ${totalPages}` : ''}
              </span>

              <button
                type="button"
                onClick={() => handlePageChange(query.page + 1)}
                disabled={!canNext || loading}
                aria-label="Página siguiente"
                className="inline-flex items-center justify-center w-8 h-8 rounded-md
                  text-on-surface-variant hover:bg-surface-container hover:text-on-surface
                  disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Icon name="chevron_right" className="text-[20px]" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
