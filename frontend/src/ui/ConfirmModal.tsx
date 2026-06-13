/**
 * ConfirmModal — Diálogo de confirmación propio del design system ActiveExam.
 *
 * Reemplaza window.confirm (popup nativo del navegador) por un modal accesible,
 * coherente con el estilo Material 3 "warm minimalism" de la app.
 *
 * Controlado: el padre maneja `abierto` y los callbacks. Cierra al click afuera
 * y con la tecla Escape. Renderiza vía createPortal a document.body para que el
 * overlay quede por encima del contenido pero por debajo del toast (z-[120]).
 */
import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Icon, Button } from './components';

export interface ConfirmModalProps {
  abierto: boolean;
  titulo: string;
  mensaje: React.ReactNode;
  textoConfirmar?: string;
  textoCancelar?: string;
  variante?: 'danger' | 'default' | 'logout';
  onConfirmar: () => void;
  onCancelar: () => void;
}

const VARIANTE_CONFIG = {
  danger: {
    icon: 'delete',
    iconWrap: 'bg-error-container text-on-error-container',
    botonVariant: 'danger' as const,
  },
  default: {
    icon: 'warning',
    iconWrap: 'bg-warning-container text-warning',
    botonVariant: 'primary' as const,
  },
  // Cerrar sesión: tono rojo, pero con icono de logout (no el triángulo de advertencia).
  logout: {
    icon: 'logout',
    iconWrap: 'bg-error-container text-on-error-container',
    botonVariant: 'danger' as const,
  },
};

export function ConfirmModal({
  abierto,
  titulo,
  mensaje,
  textoConfirmar = 'Confirmar',
  textoCancelar = 'Cancelar',
  variante = 'default',
  onConfirmar,
  onCancelar,
}: ConfirmModalProps) {
  const confirmarRef = useRef<HTMLButtonElement>(null);

  // Foco inicial en el botón confirmar + cierre con Escape.
  useEffect(() => {
    if (!abierto) return;
    confirmarRef.current?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancelar();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [abierto, onCancelar]);

  if (!abierto) return null;

  const cfg = VARIANTE_CONFIG[variante];

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-md
        bg-black/40 animate-in fade-in"
      onClick={onCancelar}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-titulo"
        className="w-full max-w-md bg-surface-container-lowest rounded-2xl shadow-card-lg
          border border-outline-variant/40 p-lg space-y-md
          animate-in zoom-in fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-md">
          <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${cfg.iconWrap}`}>
            <Icon name={cfg.icon} className="text-[22px]" fill />
          </div>
          <div className="min-w-0 space-y-base">
            <h2 id="confirm-modal-titulo" className="font-headline text-title-lg text-on-surface tracking-tight">
              {titulo}
            </h2>
            <div className="text-body-md text-on-surface-variant leading-relaxed">{mensaje}</div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-sm pt-base">
          <Button variant="ghost" size="sm" onClick={onCancelar}>
            {textoCancelar}
          </Button>
          <Button ref={confirmarRef} variant={cfg.botonVariant} size="sm" onClick={onConfirmar}>
            {textoConfirmar}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export default ConfirmModal;
