/**
 * Sistema de notificaciones TOAST global y reusable (estilo Material 3, minimalista).
 *
 * Uso:
 *   1. Envolver el árbol con <ToastProvider> y renderizar <Toaster /> una vez (en App).
 *   2. En cualquier pantalla: const toast = useToast(); toast.success('...').
 *
 * API del hook:
 *   toast.success(msg)  → ícono check_circle, color success
 *   toast.error(msg)    → ícono error, color error
 *   toast.info(msg)     → ícono info, color primary
 *   toast.show({ tipo, msg, duracion? }) → forma genérica
 *
 * Auto-dismiss ~3.5s, descartable con click/X, apilable, accesible (role=status / aria-live).
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { Icon } from '../components';

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

export type ToastTipo = 'success' | 'error' | 'info';

interface ToastItem {
  id: number;
  tipo: ToastTipo;
  msg: string;
}

interface ToastOptions {
  tipo: ToastTipo;
  msg: string;
  /** Milisegundos antes del auto-dismiss. Default 3500. 0 = no auto-dismiss. */
  duracion?: number;
}

export interface ToastApi {
  success: (msg: string, duracion?: number) => void;
  error: (msg: string, duracion?: number) => void;
  info: (msg: string, duracion?: number) => void;
  show: (opts: ToastOptions) => void;
  dismiss: (id: number) => void;
}

// ---------------------------------------------------------------------------
// Contexto
// ---------------------------------------------------------------------------

const DEFAULT_DURACION = 3500;

const ToastContext = createContext<ToastApi | null>(null);

// La pila viva se expone vía un contexto interno para que <Toaster /> la renderice.
const ToastListContext = createContext<ToastItem[]>([]);

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  // Mapa de timers para limpiar al desmontar / descartar manualmente.
  const timersRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  const show = useCallback(
    ({ tipo, msg, duracion = DEFAULT_DURACION }: ToastOptions) => {
      const id = nextId++;
      setItems((prev) => [...prev, { id, tipo, msg }]);
      if (duracion > 0) {
        const timer = setTimeout(() => dismiss(id), duracion);
        timersRef.current.set(id, timer);
      }
    },
    [dismiss],
  );

  // Limpiar todos los timers pendientes al desmontar el provider.
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach((t) => clearTimeout(t));
      timers.clear();
    };
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      success: (msg, duracion) => show({ tipo: 'success', msg, duracion }),
      error: (msg, duracion) => show({ tipo: 'error', msg, duracion }),
      info: (msg, duracion) => show({ tipo: 'info', msg, duracion }),
      show,
      dismiss,
    }),
    [show, dismiss],
  );

  return (
    <ToastContext.Provider value={api}>
      <ToastListContext.Provider value={items}>{children}</ToastListContext.Provider>
    </ToastContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast debe usarse dentro de <ToastProvider>.');
  }
  return ctx;
}

// ---------------------------------------------------------------------------
// Presentación
// ---------------------------------------------------------------------------

const TIPO_CONFIG: Record<ToastTipo, { icon: string; accent: string; iconColor: string }> = {
  // Borde de acento + color de ícono semántico, sobre surface neutro (sobrio).
  success: { icon: 'check_circle', accent: 'border-l-success', iconColor: 'text-success' },
  error: { icon: 'error', accent: 'border-l-error', iconColor: 'text-error' },
  info: { icon: 'info', accent: 'border-l-primary', iconColor: 'text-primary' },
};

function ToastCard({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  const cfg = TIPO_CONFIG[item.tipo];
  return (
    <div
      role="status"
      aria-live="polite"
      onClick={() => onDismiss(item.id)}
      className={`pointer-events-auto flex items-start gap-sm max-w-sm w-full
        bg-surface-container-lowest text-on-surface
        border border-outline-variant/40 border-l-4 ${cfg.accent}
        rounded-xl shadow-card-lg px-md py-sm cursor-pointer
        animate-in fade-in slide-in-from-bottom-4`}
    >
      <Icon name={cfg.icon} className={`text-[20px] shrink-0 mt-px ${cfg.iconColor}`} fill />
      <span className="flex-1 text-label-md leading-snug break-words">{item.msg}</span>
      <button
        type="button"
        aria-label="Descartar notificación"
        onClick={(e) => {
          e.stopPropagation();
          onDismiss(item.id);
        }}
        className="shrink-0 -mr-1 -mt-px rounded-full p-0.5 text-on-surface-variant
          hover:text-on-surface hover:bg-surface-container transition-colors"
      >
        <Icon name="close" className="text-[18px]" />
      </button>
    </div>
  );
}

/**
 * Contenedor fijo que renderiza la pila de toasts. Posicionado abajo-centro,
 * z alto para verse por encima de overlays (BiometricCapture usa z-[60]).
 */
export function Toaster() {
  const items = useContext(ToastListContext);
  const ctx = useContext(ToastContext);
  if (!ctx) return null;

  return (
    <div
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[120]
        flex flex-col items-center gap-sm w-full max-w-sm px-md pointer-events-none"
    >
      {items.map((item) => (
        <ToastCard key={item.id} item={item} onDismiss={ctx.dismiss} />
      ))}
    </div>
  );
}
