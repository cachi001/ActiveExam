import type { ReactNode } from 'react';
import { Icon } from './components';

export interface AdminColumn<T> {
  key: string;
  /** Texto o nodo React para el encabezado de la columna. */
  header: ReactNode;
  width?: string;
  align?: 'left' | 'center' | 'right';
  headerAlign?: 'left' | 'center' | 'right';
  cell: (row: T) => ReactNode;
  /** Clases extra para cada <td> de la columna (útil para sticky, fondo, etc.). */
  tdClassName?: string;
  /** Clases extra para el <th> de la columna (útil para sticky en el encabezado). */
  thClassName?: string;
}

interface AdminTableProps<T> {
  columns: AdminColumn<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  isLoading?: boolean;
  className?: string;
  tableMinWidth?: string;
  /**
   * Reparte el ancho segun los `width` de las columnas en vez de dejar que lo
   * empuje el contenido (`table-layout: fixed`), con padding mas angosto.
   * Todo sigue en UNA linea: partir un titulo en dos renglones rompe la lectura
   * vertical de la tabla.
   *
   * Con muchas columnas la tabla auto se iba a 1300px dentro de un contenedor
   * de 980, y la ultima columna de datos quedaba tapada por la de acciones, que
   * es sticky: se leia como que el texto estaba cortado.
   */
  anchoFijo?: boolean;
}

function alignClass(align?: 'left' | 'center' | 'right') {
  if (align === 'center') return 'text-center';
  if (align === 'right') return 'text-right';
  return 'text-left';
}

export function AdminTable<T>({
  columns,
  data,
  keyExtractor,
  onRowClick,
  emptyMessage = 'Sin resultados.',
  isLoading = false,
  className = '',
  tableMinWidth,
  anchoFijo = false,
}: AdminTableProps<T>) {
  return (
    <div className={`overflow-x-auto overflow-y-hidden ${className}`}>
      <table
        className={`w-full ${anchoFijo ? 'table-fixed' : ''}`}
        style={tableMinWidth ? { minWidth: tableMinWidth } : undefined}
      >
        <colgroup>
          {columns.map((col) => (
            <col key={col.key} style={col.width ? { width: col.width } : undefined} />
          ))}
        </colgroup>
        <thead>
          <tr className="bg-gray-100">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`${anchoFijo ? 'px-3' : 'px-6'} py-4 text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap bg-gray-100 ${alignClass(col.headerAlign ?? col.align)} ${col.thClassName ?? ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {isLoading && data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-6 py-12 text-center">
                <Icon name="progress_activity" className="ae-spin text-[28px] text-primary mx-auto" />
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-6 py-12 text-center">
                <div className="flex flex-col items-center gap-3">
                  <Icon name="search_off" className="text-[40px] text-gray-400" />
                  <p className="text-sm text-gray-500">{emptyMessage}</p>
                </div>
              </td>
            </tr>
          ) : (
            data.map((row) => (
              <tr
                key={keyExtractor(row)}
                className={`transition-colors hover:bg-gray-50 ${isLoading ? 'opacity-50' : ''} ${onRowClick ? 'cursor-pointer' : ''}`}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`${anchoFijo ? 'px-3' : 'px-6'} py-4 whitespace-nowrap text-sm ${alignClass(col.align)} ${col.tdClassName ?? ''}`}
                  >
                    {col.cell(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
