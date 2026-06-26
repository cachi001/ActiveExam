// Router de la app sobre `react-router-dom` (BrowserRouter → URLs limpias, sin #).
//
// Mantiene la MISMA superficie de API que el router propio anterior
// (RouterProvider, useRouter, useNavigate, useRouteParam, Routes, Link), así los
// ~25 archivos que la consumen no cambian; solo cambia la implementación interna
// y, con ella, el formato de URL (`/admin/usuarios` en vez de `#/admin/usuarios`).
//
// DEPLOY: BrowserRouter exige que el host sirva `index.html` para cualquier ruta
// (SPA fallback). El dev server de Vite ya lo hace; en Vercel está el rewrite de
// `vercel.json` (`/(.*) -> /index.html`). Sin ese fallback, un F5 en una ruta
// profunda daría 404.
import { useCallback, useEffect, type ReactNode } from 'react';
import {
  BrowserRouter,
  Routes as RouterRoutes,
  Route,
  Link as RouterLink,
  useLocation,
  useNavigate as useRouterNavigate,
  useParams,
} from 'react-router-dom';

export function RouterProvider({ children }: { children: ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>;
}

/**
 * Navegación con la firma `(to: string) => void` que usa toda la app. Normaliza
 * para que siempre sea absoluta (el router anterior aceptaba paths sin `/` inicial
 * y los trataba como absolutos; react-router-dom los trataría como relativos).
 */
export function useNavigate() {
  const navigate = useRouterNavigate();
  return useCallback(
    (to: string) => navigate(to.startsWith('/') ? to : '/' + to),
    [navigate],
  );
}

export function useRouter() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  return { path: pathname, navigate };
}

/** Lee un parámetro de ruta dinámico (p.ej. `/admin/usuarios/:id` → useRouteParam('id')). */
export function useRouteParam(name: string): string | null {
  const params = useParams();
  return params[name] ?? null;
}

/** Sube el scroll al tope en cada cambio de ruta (lo hacía el navigate anterior). */
function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
  }, [pathname]);
  return null;
}

/**
 * Renderiza el match de un mapa `{ ruta: nodo }`. Las claves son patrones de
 * react-router-dom: estáticos (`/admin/usuarios`) o con parámetro (`/admin/usuarios/:id`).
 * `fallback` se usa para cualquier ruta no matcheada (`*`).
 */
export function Routes({ routes, fallback }: { routes: Record<string, ReactNode>; fallback?: ReactNode }) {
  return (
    <>
      <ScrollToTop />
      <RouterRoutes>
        {Object.entries(routes).map(([pattern, node]) => (
          <Route key={pattern} path={pattern} element={<>{node}</>} />
        ))}
        <Route path="*" element={<>{fallback ?? null}</>} />
      </RouterRoutes>
    </>
  );
}

export function Link({ to, className, children, onClick }: {
  to: string; className?: string; children: ReactNode; onClick?: () => void;
}) {
  return (
    <RouterLink to={to} className={className} onClick={onClick ? () => onClick() : undefined}>
      {children}
    </RouterLink>
  );
}
