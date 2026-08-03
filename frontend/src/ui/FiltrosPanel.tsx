/**
 * FiltrosPanel — panel de filtros GENÉRICO y reutilizable.
 *
 * Provee el "chrome" común de cualquier barra de filtros: encabezado "Filtros",
 * un slot para los campos (children) y las acciones Aplicar / Limpiar. NO conoce
 * qué se filtra — cada pantalla arma sus propios inputs y decide qué hacer al
 * aplicar. Pensado para reusarse en listados (exámenes, usuarios, sesiones…).
 *
 * Los botones de EXPORT NO viven acá: son acciones de la pantalla, no del filtro.
 */
import type { ReactNode } from 'react';
import { Icon } from './components';

export interface FiltrosPanelProps {
  /** Título del panel. Default "Filtros". */
  titulo?: string;
  /** Los campos de filtro (selects, inputs, …). */
  children: ReactNode;
  /** Se dispara al presionar "Aplicar filtros". */
  onAplicar: () => void;
  /** Se dispara al presionar "Limpiar" (si se pasa y `hayFiltros`). */
  onLimpiar?: () => void;
  /** Muestra el botón "Limpiar" cuando hay filtros activos. */
  hayFiltros?: boolean;
  /**
   * Hay cambios pendientes de aplicar (el borrador difiere de lo aplicado). El
   * botón "Aplicar filtros" SOLO aparece cuando esto es true — si no cambiaste
   * nada, no hay nada que aplicar. Default true (retrocompat).
   */
  hayCambios?: boolean;
  /** Deshabilita "Aplicar" (p. ej. mientras carga). */
  aplicarDeshabilitado?: boolean;
}

export function FiltrosPanel({
  titulo = 'Filtros',
  children,
  onAplicar,
  onLimpiar,
  hayFiltros = false,
  hayCambios = true,
  aplicarDeshabilitado = false,
}: FiltrosPanelProps) {
  return (
    <section
      className="rounded-2xl border border-surface-200 bg-white px-lg py-md shadow-card"
      aria-label={titulo}
    >
      <div className="flex items-center gap-2 mb-md">
        <Icon name="filter_alt" className="text-[18px] text-on-surface-variant" />
        <h2 className="text-[14px] font-semibold text-on-surface">{titulo}</h2>
      </div>

      <div className="flex flex-wrap items-end gap-md">
        {children}

        <div className="ml-auto flex items-end gap-2">
          {hayFiltros && onLimpiar && (
            <button
              type="button"
              onClick={onLimpiar}
              className="rounded-md px-3 py-2 text-[13px] font-medium text-on-surface-variant hover:bg-surface-100"
            >
              Limpiar
            </button>
          )}
          {hayCambios && (
            <button
              type="button"
              onClick={onAplicar}
              disabled={aplicarDeshabilitado}
              className="rounded-md bg-primary px-4 py-2 text-[13px] font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
            >
              Aplicar filtros
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

export default FiltrosPanel;
