// Paginación reutilizable de staff. Patrón: primera / anterior / números (con
// ventana y elipsis) / siguiente / última, resumen "Mostrando X–Y de Z · Página
// N de M", y selector opcional de tamaño de página.
//
// Adaptado al design system del proyecto (Material Symbols vía <Icon>, tokens
// surface-*/on-surface/primary). `currentPage` es 1-indexed (1 = primera página).
import { useMemo } from 'react';
import { Icon } from './components';

export interface PaginationProps {
  /** Página actual, 1-indexed (1 = primera página). */
  currentPage: number;
  totalPages: number;
  totalElements: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  /** Si se pasa, muestra el selector de "por página". */
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
  className?: string;
}

/** Ventana de páginas visibles con elipsis: 1 … 4 [5] 6 … 20. Todo 1-based. */
export function paginasVisibles(actual: number, total: number): Array<number | '…'> {
  if (total <= 4) return Array.from({ length: total }, (_, i) => i + 1);
  const primera = 1;
  const ultima = total;
  if (actual <= 2) return [primera, 2, 3, '…', ultima];
  if (actual === 3) return [primera, 2, 3, 4, '…', ultima];
  if (actual >= ultima - 1) return [primera, '…', ultima - 2, ultima - 1, ultima];
  if (actual === ultima - 2) return [primera, '…', ultima - 3, ultima - 2, ultima - 1, ultima];
  return [primera, '…', actual - 1, actual, actual + 1, '…', ultima];
}

const navBtn =
  'inline-flex h-8 w-8 items-center justify-center rounded-md border border-surface-200 bg-white text-on-surface-variant hover:bg-surface-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors';

/** Selector "Por página" reutilizable — pensado para el header de una tabla
 * (alineado a la derecha con `className="ml-auto"`), no dentro de la paginación. */
export function PageSizeSelect({
  value,
  onChange,
  options = [5, 10, 20, 50],
  className = '',
}: {
  value: number;
  onChange: (size: number) => void;
  options?: number[];
  className?: string;
}) {
  return (
    <label className={`flex items-center gap-2 whitespace-nowrap text-[13px] font-normal text-on-surface-variant ${className}`}>
      <span>Por página</span>
      <select
        className="cursor-pointer rounded-md border border-surface-200 bg-white px-2 py-1 text-[13px] text-on-surface focus:border-primary focus:outline-none"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {options.map((op) => (
          <option key={op} value={op}>{op}</option>
        ))}
      </select>
    </label>
  );
}

export function Pagination({
  currentPage,
  totalPages,
  totalElements,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [5, 10, 20, 50],
  className = '',
}: PaginationProps) {
  const totalPaginas = Math.max(1, totalPages);
  const paginaSegura = Math.min(Math.max(1, currentPage), totalPaginas);

  const { desde, hasta } = useMemo(() => {
    if (totalElements === 0) return { desde: 0, hasta: 0 };
    return {
      desde: (paginaSegura - 1) * pageSize + 1,
      hasta: Math.min(totalElements, paginaSegura * pageSize),
    };
  }, [totalElements, paginaSegura, pageSize]);

  const paginas = useMemo(() => paginasVisibles(paginaSegura, totalPaginas), [paginaSegura, totalPaginas]);
  const puedeAnterior = paginaSegura > 1;
  const puedeSiguiente = paginaSegura < totalPaginas;

  return (
    <div
      className={`flex flex-col gap-3 rounded-2xl border border-surface-200 bg-white px-lg py-3 text-[13px] text-on-surface-variant shadow-card sm:flex-row sm:items-center sm:justify-between ${className}`}
    >
      <span>
        Mostrando <strong className="text-on-surface tabular-nums">{desde}–{hasta}</strong> de{' '}
        <strong className="text-on-surface tabular-nums">{totalElements}</strong> · Página{' '}
        <strong className="text-on-surface tabular-nums">{paginaSegura}</strong> de{' '}
        <strong className="text-on-surface tabular-nums">{totalPaginas}</strong>
      </span>

      <div className="flex items-center gap-3">
        {onPageSizeChange && (
          <label className="hidden items-center gap-2 whitespace-nowrap sm:flex">
            <span>Por página</span>
            <select
              className="cursor-pointer rounded-md border border-surface-200 bg-white px-2 py-1 text-[13px] text-on-surface focus:border-primary focus:outline-none"
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
            >
              {pageSizeOptions.map((op) => (
                <option key={op} value={op}>{op}</option>
              ))}
            </select>
          </label>
        )}

        <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(1)}
          disabled={!puedeAnterior}
          className={`${navBtn} hidden sm:inline-flex`}
          aria-label="Primera página"
        >
          <Icon name="first_page" className="text-[18px]" />
        </button>
        <button
          type="button"
          onClick={() => onPageChange(paginaSegura - 1)}
          disabled={!puedeAnterior}
          className={navBtn}
          aria-label="Página anterior"
        >
          <Icon name="chevron_left" className="text-[18px]" />
        </button>

        <div className="mx-1 flex items-center gap-1">
          {paginas.map((p, i) =>
            p === '…' ? (
              <span key={`e${i}`} className="select-none px-1.5 text-on-surface-variant">…</span>
            ) : (
              <button
                key={p}
                type="button"
                onClick={() => onPageChange(p)}
                aria-current={p === paginaSegura ? 'page' : undefined}
                className={`h-8 min-w-8 rounded-md px-2 font-semibold tabular-nums transition-colors ${
                  p === paginaSegura
                    ? 'bg-primary text-white'
                    : 'border border-surface-200 bg-white text-on-surface hover:bg-surface-100'
                }`}
              >
                {p}
              </button>
            ),
          )}
        </div>

        <button
          type="button"
          onClick={() => onPageChange(paginaSegura + 1)}
          disabled={!puedeSiguiente}
          className={navBtn}
          aria-label="Página siguiente"
        >
          <Icon name="chevron_right" className="text-[18px]" />
        </button>
        <button
          type="button"
          onClick={() => onPageChange(totalPaginas)}
          disabled={!puedeSiguiente}
          className={`${navBtn} hidden sm:inline-flex`}
          aria-label="Última página"
        >
          <Icon name="last_page" className="text-[18px]" />
        </button>
        </div>
      </div>
    </div>
  );
}

export default Pagination;
