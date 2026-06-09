/**
 * ActionMenu — menú de acciones "kebab" (3 puntitos) con popup.
 *
 * Patrón de tabla del sistema de reservas: en vez de botones inline por fila,
 * un único botón ⋮ que despliega las acciones. Cierra con Escape o click afuera.
 */
import { useState, useEffect } from 'react';
import { Icon } from './components';

export interface ActionItem {
  label: string;
  icon?: string;
  onClick: () => void;
  danger?: boolean;
}

export function ActionMenu({ items, ariaLabel = 'Acciones' }: { items: ActionItem[]; ariaLabel?: string }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <div className="relative inline-block text-left">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={ariaLabel}
        className="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
      >
        <Icon name="more_vert" className="text-[20px]" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div
            role="menu"
            className="absolute right-0 top-full mt-1 z-50 w-44 rounded-xl border border-outline-variant/60 bg-white shadow-card-lg overflow-hidden py-1 animate-in fade-in slide-in-from-top-1 duration-150"
          >
            {items.map((it, i) => (
              <button
                key={i}
                type="button"
                role="menuitem"
                onClick={() => { setOpen(false); it.onClick(); }}
                className={`w-full flex items-center gap-2.5 px-3 py-2 text-[13px] text-left transition-colors ${
                  it.danger ? 'text-error hover:bg-error-container/40' : 'text-on-surface hover:bg-surface-container'
                }`}
              >
                {it.icon && <Icon name={it.icon} className="text-[18px] shrink-0" />}
                {it.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default ActionMenu;
