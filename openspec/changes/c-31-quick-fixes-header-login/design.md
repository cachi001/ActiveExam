## Approach

Dos eliminaciones quirúrgicas de JSX estático. Sin lógica nueva, sin nuevos componentes, sin cambios de rutas ni de estado.

### Fix 1 — Header de staff (`shells.tsx`)

**Antes**:
```tsx
<span className="inline-flex items-center gap-base text-label-sm text-on-surface-variant bg-surface-container px-sm py-base rounded-full">
  <Icon name="dns" className="text-[16px]" /> Self-hosted · {INSTITUTION.nombreCorto}
</span>
```

**Después**: El badge completo se elimina. El ícono `dns` (servidor) sin la etiqueta "Self-hosted" pierde significado para el usuario final (es jerga de infraestructura). El `nombreCorto` de la institución ya aparece en la sidebar (logo + nombre), por lo que no se pierde contexto. El `<div className="flex items-center gap-sm">` del header queda vacío si no hay otro contenido; se puede dejar o eliminar — se elimina para no dejar markup muerto.

**Decisión**: Eliminar el `<span>` del badge entero y el `<div>` contenedor si queda vacío.

### Fix 2 — Login nav (`Login.tsx`)

**Antes**:
```tsx
<nav className="flex justify-center items-center gap-lg border-t border-outline-variant/60 pt-lg">
  <a className="text-label-md text-primary hover:underline" href="#/requisitos">Requisitos técnicos</a>
  <span className="w-1 h-1 bg-outline-variant rounded-full" />
  <a className="text-label-md text-primary hover:underline" href="#/">Necesito ayuda</a>
</nav>
```

**Después**: Queda solo el link "Necesito ayuda". El `<span>` separador se elimina junto con el link de requisitos.

```tsx
<nav className="flex justify-center items-center gap-lg border-t border-outline-variant/60 pt-lg">
  <a className="text-label-md text-primary hover:underline" href="#/">Necesito ayuda</a>
</nav>
```

**Por qué no eliminar la ruta `/requisitos` de App.tsx**: la ruta puede ser útil en el futuro flujo real (verificación de equipo antes del examen); por ahora simplemente no se expone en el login.

## Files Affected

| File | Change |
|------|--------|
| `frontend/src/ui/shells.tsx` | Eliminar badge "Self-hosted" (línea ~114-116) y `<div>` contenedor vacío resultante |
| `frontend/src/screens/Login.tsx` | Eliminar `<a href="#/requisitos">` y el `<span>` separador (líneas ~60-61) |

## Testing

- `npx tsc --noEmit` en 0 errores
- Grep: `Self-hosted` no aparece en `frontend/src/`
- Grep: `#/requisitos` no aparece en `frontend/src/screens/Login.tsx`
- Visual: el header de staff muestra solo el título de la página; el login muestra solo "Necesito ayuda" en el nav
