/**
 * ActionMenu — menú de acciones "kebab" (3 puntitos) con popup.
 *
 * Patrón de tabla: en vez de botones inline por fila, un único botón ⋮ que
 * despliega las acciones. Cierra con Escape o click afuera o scroll.
 *
 * El dropdown se posiciona con `position: fixed` calculado desde el rect del
 * botón trigger, por lo que nunca queda recortado por `overflow-hidden` del
 * contenedor ancestro (p.ej. la tabla de GestionUsuarios).
 *
 * Flip inteligente: si abajo del botón no hay suficiente espacio para el menú,
 * se abre hacia arriba (anclado al borde superior del botón).
 */
import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from './components';

export interface ActionItem {
  label: string;
  icon?: string;
  onClick: () => void;
  danger?: boolean;
  /**
   * Una acción que no aplica se muestra APAGADA, no se saca del menú: si en una
   * fila hay tres opciones y en la de al lado dos, lo primero que se piensa es
   * que la pantalla se rompió. Apagada además deja lugar para explicar por qué,
   * que es la información que hace falta.
   */
  disabled?: boolean;
  /** Por qué está apagada. Se muestra al pasar el mouse. */
  title?: string;
}

/** Alto estimado del menú en px (40px cabecera + 36px×n ítems + padding). */
const MENU_ITEM_HEIGHT = 36;
const MENU_PADDING = 8;
const MENU_GAP = 4;

export function ActionMenu({ items, ariaLabel = 'Acciones' }: { items: ActionItem[]; ariaLabel?: string }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top?: number; bottom?: number; right: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  function openMenu() {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    const estimatedMenuHeight = items.length * MENU_ITEM_HEIGHT + MENU_PADDING;
    const spaceBelow = window.innerHeight - rect.bottom;
    const opensUpward = spaceBelow < estimatedMenuHeight + MENU_GAP;
    setPos(
      opensUpward
        ? {
            // Anclar la parte inferior del menú al borde superior del botón
            bottom: window.innerHeight - rect.top + MENU_GAP,
            right: window.innerWidth - rect.right,
          }
        : {
            top: rect.bottom + MENU_GAP,
            right: window.innerWidth - rect.right,
          },
    );
    setOpen(true);
  }

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    const onScroll = () => setOpen(false);
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [open]);

  const dropdown = open && pos ? (
    <>
      <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
      <div
        role="menu"
        style={{ top: pos.top, bottom: pos.bottom, right: pos.right, position: 'fixed' }}
        className={`z-50 w-44 rounded-xl border border-outline-variant/60 bg-white shadow-card-lg overflow-hidden py-1 animate-in fade-in duration-150 ${
          pos.bottom != null ? 'slide-in-from-bottom-1' : 'slide-in-from-top-1'
        }`}
      >
        {items.map((it, i) => (
          <button
            key={i}
            type="button"
            role="menuitem"
            disabled={it.disabled}
            title={it.title}
            onClick={() => { if (it.disabled) return; setOpen(false); it.onClick(); }}
            className={`w-full flex items-center gap-2.5 px-3 py-2 text-[13px] text-left transition-colors ${
              it.disabled
                ? 'text-on-surface-variant/40 cursor-not-allowed'
                : it.danger
                  ? 'text-error hover:bg-error-container/40'
                  : 'text-on-surface hover:bg-surface-container'
            }`}
          >
            {it.icon && <Icon name={it.icon} className="text-[18px] shrink-0" />}
            {it.label}
          </button>
        ))}
      </div>
    </>
  ) : null;

  return (
    <div className="relative inline-block text-left">
      <button
        ref={btnRef}
        type="button"
        onClick={openMenu}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={ariaLabel}
        className="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
      >
        <Icon name="more_vert" className="text-[20px]" />
      </button>

      {createPortal(dropdown, document.body)}
    </div>
  );
}

export default ActionMenu;
