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

/** Renderiza el primer match exacto del mapa de rutas, o el fallback. */
export function Routes({ routes, fallback }: { routes: Record<string, ReactNode>; fallback?: ReactNode }) {
  const { path } = useRouter();
  if (routes[path]) return <>{routes[path]}</>;
  return <>{fallback ?? null}</>;
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
