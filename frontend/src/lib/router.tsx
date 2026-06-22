// Router mínimo basado en hash (#/ruta). Sin dependencias externas: funciona
// con `vite dev` y con build estático sin configurar el servidor.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

interface RouterCtx {
  path: string;
  navigate: (to: string) => void;
}

const Ctx = createContext<RouterCtx>({ path: '/', navigate: () => {} });

function currentHashPath(): string {
  const h = window.location.hash.replace(/^#/, '');
  return h.startsWith('/') ? h : '/' + h;
}

export function RouterProvider({ children }: { children: ReactNode }) {
  const [path, setPath] = useState<string>(() => (window.location.hash ? currentHashPath() : '/'));

  useEffect(() => {
    const onHash = () => setPath(currentHashPath());
    window.addEventListener('hashchange', onHash);
    if (!window.location.hash) window.location.hash = '#/';
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const navigate = useCallback((to: string) => {
    const norm = to.startsWith('/') ? to : '/' + to;
    if (currentHashPath() !== norm) window.location.hash = '#' + norm;
    else setPath(norm);
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
  }, []);

  const value = useMemo(() => ({ path, navigate }), [path, navigate]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useRouter() { return useContext(Ctx); }

export function useNavigate() { return useContext(Ctx).navigate; }

/**
 * Renderiza el primer match del mapa de rutas.
 *
 * Matching en orden:
 * 1. Exact match: `routes[path]` — preserva el comportamiento original.
 * 2. Prefix match con parámetro: si una clave termina en `/:param`, intenta
 *    matchear `path` como `prefix/<valor>` y pasa el valor via sessionStorage
 *    bajo la clave `router_param_<param>`. Esto es minimal y seguro — no rompe
 *    el matching exacto.
 * 3. Fallback.
 */
export function Routes({ routes, fallback }: { routes: Record<string, ReactNode>; fallback?: ReactNode }) {
  const { path } = useRouter();
  // 1. Exact match (comportamiento original, intacto)
  if (routes[path]) return <>{routes[path]}</>;
  // 2. Prefix match con parámetro dinámico (/:param al final de la clave)
  for (const [pattern, node] of Object.entries(routes)) {
    const paramMatch = pattern.match(/^(.*)\/:([^/]+)$/);
    if (!paramMatch) continue;
    const [, prefix, paramName] = paramMatch;
    if (path.startsWith(prefix + '/')) {
      const paramValue = path.slice(prefix.length + 1);
      if (paramValue && !paramValue.includes('/')) {
        try { sessionStorage.setItem(`router_param_${paramName}`, paramValue); } catch { /* ignore */ }
        return <>{node}</>;
      }
    }
  }
  return <>{fallback ?? null}</>;
}

/** Lee un parámetro de ruta dinámico guardado por Routes. */
export function useRouteParam(name: string): string | null {
  try { return sessionStorage.getItem(`router_param_${name}`); } catch { return null; }
}

export function Link({ to, className, children, onClick }: {
  to: string; className?: string; children: ReactNode; onClick?: () => void;
}) {
  const navigate = useNavigate();
  return (
    <a
      href={'#' + to}
      className={className}
      onClick={(e) => { e.preventDefault(); onClick?.(); navigate(to); }}
    >
      {children}
    </a>
  );
}
