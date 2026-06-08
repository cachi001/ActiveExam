/**
 * HelpButton — botón "?" con popover/modal de ayuda contextual.
 *
 * Uso:
 *   <HelpButton title="Supervisión en vivo">
 *     Mostrá acá lo que hace la página, qué ve el usuario y qué decisiones puede tomar.
 *   </HelpButton>
 *
 * Patrón consciente:
 *   - Pequeño, no invasivo (icono "help" redondo en el header de la página).
 *   - Modal accesible (Esc cierra, click fuera cierra).
 *   - Sin dependencias externas; sólo Tailwind + estado React local.
 *   - **Portal al body**: el modal se monta fuera del árbol de la página para que
 *     `position: fixed` quede relativo al viewport. De lo contrario, cualquier
 *     ancestro con `transform`/`filter` (p.ej. las animaciones `animate-in` de
 *     tailwindcss-animate) lo recorta y deja visibles el header y la sidebar.
 *   - Mientras está abierto, bloquea el scroll del body para que sidebar/header
 *     pegajosos no compitan visualmente con el overlay.
 */
import { useEffect, useId, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from './components';

interface HelpButtonProps {
  /** Título grande del modal (ej. "Supervisión en vivo"). */
  title: string;
  /** Contenido explicativo del modal — JSX libre. */
  children: ReactNode;
  /** Tooltip del botón (defecto "Ayuda de esta página"). */
  ariaLabel?: string;
  /** Clase adicional para alinear el botón en distintos headers. */
  className?: string;
}

export function HelpButton({ title, children, ariaLabel, className = '' }: HelpButtonProps) {
  const [abierto, setAbierto] = useState(false);
  const dialogId = useId();

  // Esc cierra + bloquear scroll del body mientras está abierto (evita que el
  // header pegajoso y la sidebar queden "vibrando" sobre el overlay).
  useEffect(() => {
    if (!abierto) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setAbierto(false);
    }
    document.addEventListener('keydown', onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [abierto]);

  const overlay = abierto ? (
    <div
      // z-[1000] para superar cualquier z-index sticky del shell (header z-30,
      // drawer mobile z-50, banners). bg-black/60 + backdrop-blur-md le da
      // contraste suficiente para apagar header/sidebar de fondo.
      className="fixed inset-0 z-[1000] flex items-center justify-center p-md
        bg-black/60 backdrop-blur-md animate-in fade-in duration-150"
      onClick={() => setAbierto(false)}
    >
      <div
        id={dialogId}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${dialogId}-title`}
        className="relative w-full max-w-md max-h-[80vh] flex flex-col bg-surface-container-lowest
          rounded-2xl shadow-2xl border border-outline-variant/40 overflow-hidden
          animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-md px-lg py-md border-b border-outline-variant/40 shrink-0">
          <div className="flex items-center gap-sm">
            <span className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-primary-fixed text-primary">
              <Icon name="help" className="text-[20px]" />
            </span>
            <h2 id={`${dialogId}-title`} className="font-headline text-title-md text-on-surface">
              {title}
            </h2>
          </div>
          <button
            type="button"
            onClick={() => setAbierto(false)}
            aria-label="Cerrar ayuda"
            className="w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant
              hover:bg-surface-container focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <Icon name="close" className="text-[20px]" />
          </button>
        </div>

        <div className="overflow-y-auto px-lg py-md text-body-md text-on-surface-variant space-y-sm leading-relaxed">
          {children}
        </div>
      </div>
    </div>
  ) : null;

  return (
    <>
      <button
        type="button"
        onClick={() => setAbierto(true)}
        aria-label={ariaLabel ?? 'Ayuda de esta página'}
        aria-haspopup="dialog"
        aria-expanded={abierto}
        aria-controls={dialogId}
        className={`inline-flex items-center justify-center w-9 h-9 rounded-full
          bg-surface-container-low text-on-surface-variant border border-outline-variant/40
          hover:bg-surface-container hover:text-primary
          focus:outline-none focus:ring-2 focus:ring-primary/40
          transition-colors ${className}`}
      >
        <Icon name="help" className="text-[20px]" />
      </button>

      {/* Montaje en portal al body: escapa de cualquier ancestro con transform/
          filter que recorte el `position: fixed`. */}
      {overlay && typeof document !== 'undefined'
        ? createPortal(overlay, document.body)
        : null}
    </>
  );
}

export default HelpButton;
