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

export type ToastTipo = 'success' | 'error' | 'info' | 'warning';

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
  warning: (msg: string, duracion?: number) => void;
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
      warning: (msg, duracion) => show({ tipo: 'warning', msg, duracion }),
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

const TIPO_CONFIG: Record<ToastTipo, { icon: string; bg: string; border: string; iconColor: string; textColor: string }> = {
  // Estilo "card tintada suave" (fondo -50, borde -200, ícono -600, texto -900),
  // tomado del sistema de referencia.
  success: { icon: 'check_circle', bg: 'bg-success-50', border: 'border-success-200', iconColor: 'text-success-600', textColor: 'text-success-900' },
  error: { icon: 'cancel', bg: 'bg-error-50', border: 'border-error-200', iconColor: 'text-error-600', textColor: 'text-error-900' },
  info: { icon: 'info', bg: 'bg-primary-50', border: 'border-primary-200', iconColor: 'text-primary-600', textColor: 'text-primary-900' },
  warning: { icon: 'warning', bg: 'bg-warning-50', border: 'border-warning-200', iconColor: 'text-warning-600', textColor: 'text-warning-900' },
};

function ToastCard({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  const cfg = TIPO_CONFIG[item.tipo];
  return (
    <div
      role="status"
      aria-live="polite"
      className={`pointer-events-auto flex items-start gap-3 w-full min-w-[300px] max-w-[400px]
        border ${cfg.bg} ${cfg.border}
        rounded-xl shadow-lg p-4
        animate-in fade-in slide-in-from-right-8 duration-300`}
    >
      <Icon name={cfg.icon} className={`text-[20px] shrink-0 mt-0.5 ${cfg.iconColor}`} fill />
      <span className={`flex-1 min-w-0 text-sm font-medium leading-snug break-words ${cfg.textColor}`}>{item.msg}</span>
      <button
        type="button"
        aria-label="Descartar notificación"
        onClick={(e) => {
          e.stopPropagation();
          onDismiss(item.id);
        }}
        className="shrink-0 -mr-1 -mt-0.5 rounded-lg p-1 text-on-surface-variant
          hover:text-on-surface hover:bg-black/5 transition-colors cursor-pointer"
      >
        <Icon name="close" className="text-[16px]" />
      </button>
    </div>
  );
}

/**
 * Contenedor fijo que renderiza la pila de toasts. Posicionado arriba-derecha
 * (convención estándar de notificaciones), z alto para verse por encima de
 * overlays (BiometricCapture usa z-[60]).
 */
export function Toaster() {
  const items = useContext(ToastListContext);
  const ctx = useContext(ToastContext);
  if (!ctx) return null;

  return (
    <div
      // Anclado a top-right de la VENTANA. `right-0` + `pr-4`/`pt-4` evita conflictos
      // con shells mobile que recortan el padding. Respeta safe-area iOS.
      style={{
        paddingTop: 'max(1rem, env(safe-area-inset-top))',
        paddingRight: 'max(1rem, env(safe-area-inset-right))',
      }}
      className="fixed top-0 right-0 z-[120]
        flex flex-col items-end gap-sm w-full max-w-sm pointer-events-none"
    >
      {items.map((item) => (
        <ToastCard key={item.id} item={item} onDismiss={ctx.dismiss} />
      ))}
    </div>
  );
}
