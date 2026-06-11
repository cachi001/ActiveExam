# Tasks: c-31-quick-fixes-header-login

## Fix 1 — Eliminar badge "Self-hosted" del header de staff

- [x] T-01: En `frontend/src/ui/shells.tsx`, eliminar el `<span>` del badge (ícono `dns` + texto "Self-hosted · {INSTITUTION.nombreCorto}") y el `<div className="flex items-center gap-sm">` contenedor que queda vacío.
- [x] T-02: Verificar que `INSTITUTION` sigue importado y usado en otros lugares del archivo (no eliminar la importación si está en uso).

## Fix 2 — Eliminar link "Requisitos técnicos" del login

- [x] T-03: En `frontend/src/screens/Login.tsx`, eliminar la línea `<a className="text-label-md text-primary hover:underline" href="#/requisitos">Requisitos técnicos</a>`.
- [x] T-04: Eliminar el `<span className="w-1 h-1 bg-outline-variant rounded-full" />` separador que quedaba entre los dos links.
- [x] T-05: Verificar que el `<nav>` resultante contiene solo el link "Necesito ayuda" y no quedan separadores huérfanos.

## Verificación

- [x] T-06: `grep -r "Self-hosted" frontend/src/` → sin resultados (o solo en comentarios).
- [x] T-07: Verificar que `#/requisitos` no aparece en `frontend/src/screens/Login.tsx`.
- [x] T-08: `npx tsc --noEmit` desde `frontend/` → 0 errores.

## CHANGES.md

- [x] T-09: Registrar C-31 en CHANGES.md (subsección "Refinamiento post-fundación"), con estado `[x]` y descripción de los 2 fixes.
