## Context

El design system de ActiveExam (Tailwind + Material 3 tokens) está sólido en colores, tipografía y radios, pero el componente `Button` tiene un único tamaño (`h-12 px-lg`) que obliga a parches ad-hoc con `className`. Varios strings de UI muestran términos de desarrollo ("demo", "stub", "Ej:") visibles al usuario final; algunos son solo etiquetas descuidadas, otros son disclaimers legales L2.5 que deben reformularse sin perder su significado. Las herramientas de desarrollo (ScreenNavigator flotante, botón de simulación de deriva de embedding) no tienen control de visibilidad y aparecen en cualquier entorno. Los formularios (ConfigureExam, futuras pantallas) usan un componente `Field` local y sliders ad-hoc sin consistencia.

**Estado actual relevante:**

| Archivo | Problema |
|---|---|
| `ui/components.tsx:25-39` | Button: un solo tamaño `h-12 px-lg`, sin prop `size` |
| `screens/Login.tsx:49` | `h-14` hardcodeado sobre Button |
| `screens/AdminDashboard.tsx:57-59` | 3 botones `w-full` apilados sin gap |
| `screens/ConfigureExam.tsx:41,46` | `placeholder="Ej: ..."` visible al usuario |
| `screens/StudentProfile.tsx:595,602` | "Control de demostración" / "Demo: simular deriva embedding" |
| `screens/StudentProfile.tsx:688` | "Disponible próximamente" (neutro pero puede reformularse) |
| `screens/EquipmentCheck.tsx:107` | "(modo demo)" en mensaje de fallas |
| `screens/enrollment/EnrollmentDniStep.tsx:134` | "Datos extraídos por OCR (demo)" |
| `screens/enrollment/EnrollmentDniStep.tsx:205` | "Análisis indicativo (demo)" — encabezado del disclaimer L2.5 |
| `screens/AdminDetectionHarness.tsx:863` | "Las señales de visión siguen siendo del stub" |
| `ui/ScreenNavigator.tsx:70,79` | `title="Navegador de pantallas (demo)"` / `'Modo demo'` como texto visible |
| `App.tsx:59` | `<ScreenNavigator />` renderizado incondicionalmente |

## Goals / Non-Goals

**Goals:**

- API de Button con `size?: 'sm' | 'md' | 'lg'` usando tokens del design system; retrocompatible (default `'md'`).
- Componentes reutilizables `FormField` y `RangeInput` en `ui/` para uso en ConfigureExam y pantallas futuras.
- Flag `VITE_DEV_TOOLS` (string `'1'`/`'0'`, default `'0'`) que condiciona ScreenNavigator y el bloque de simulación de deriva. Visible en `src/lib/devConfig.ts` (o equivalente).
- Limpieza de 7 strings de UI con jerga; los disclaimers L2.5 se conservan íntegramente (RN-GLB-01, L2.5).
- Corrección de stacks de botones sin gap (AdminDashboard mínimo; otros cuando aplique).

**Non-Goals:**

- Rediseño visual de pantallas completas (eso es scope de changes posteriores de la tanda UI).
- Cambios de comportamiento funcional. Solo presentación y estructura de componentes.
- Agregar dark mode o theming dinámico.
- Ocultar AdminDetectionHarness (es una herramienta admin legítima, no de desarrollo).
- Modificar la lógica de proctoring, biometría o transporte.

## Decisions

### D-1: API del componente Button con `size`

**Decisión**: Agregar `size?: 'sm' | 'md' | 'lg'` como prop al componente `Button`. Los tamaños mapean a tokens del design system:

| size | height | padding-x | uso típico |
|------|--------|-----------|-----------|
| `sm` | `h-9` | `px-md` | acciones secundarias compactas, botones en cards densas |
| `md` | `h-12` | `px-lg` | acción principal estándar (default — sin cambio) |
| `lg` | `h-14` | `px-xl` | CTA de pantalla completa (normaliza Login.tsx) |

Implementación: mapa `SIZE_CLASSES` interno en `Button`; la prop se extrae junto a `variant`, `icon`, `iconRight`. El `className` externo se aplica al final (override permitido, pero desaconsejado para tamaño).

**Alternativa descartada**: usar solo `className` para tamaños (ya es lo que hace el código hoy y produce inconsistencias).

**Alternativa descartada**: CVA (class-variance-authority) — agrega una dependencia por algo que resuelve un mapa literal de 3 entradas.

### D-2: Primitiva `FormField`

**Decisión**: Componente en `ui/components.tsx`:

```tsx
interface FormFieldProps {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}

export function FormField({ label, hint, error, children, className = '' }: FormFieldProps) {
  return (
    <div className={`space-y-base ${className}`}>
      <label className="text-label-sm uppercase tracking-wide text-on-surface-variant font-semibold">
        {label}
      </label>
      {children}
      {hint && !error && <p className="text-label-sm text-on-surface-variant">{hint}</p>}
      {error && <p className="text-label-sm text-error">{error}</p>}
    </div>
  );
}
```

Reemplaza el componente `Field` local de ConfigureExam (idéntico en función, ahora exportado y reutilizable).

### D-3: Primitiva `RangeInput`

**Decisión**: Componente en `ui/components.tsx` para sliders con label dinámico:

```tsx
interface RangeInputProps {
  label: string;           // ej: "Duración" (sin valor — el componente lo agrega)
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;           // ej: "minutos", "%"
  hint?: string;
  onChange: (v: number) => void;
}

export function RangeInput({ label, value, min, max, step = 1, unit = '', hint, onChange }: RangeInputProps) {
  return (
    <FormField label={`${label}: ${value}${unit ? ' ' + unit : ''}`} hint={hint}>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-primary"
      />
    </FormField>
  );
}
```

Unifica el `accent-[#5b5bd6]` hardcodeado a `accent-primary` (token del design system).

### D-4: Flag `VITE_DEV_TOOLS`

**Decisión**: Variable de entorno Vite (`import.meta.env.VITE_DEV_TOOLS`). Se expone como constante booleana en un módulo pequeño:

```ts
// src/lib/devConfig.ts
export const DEV_TOOLS_ENABLED = import.meta.env.VITE_DEV_TOOLS === '1';
```

Uso en App.tsx:
```tsx
{DEV_TOOLS_ENABLED && <ScreenNavigator />}
```

Uso en StudentProfile.tsx (bloque simular deriva):
```tsx
{DEV_TOOLS_ENABLED && biometriaOk && !biometriaCaducada && !biometriaRenovacionRequerida && (
  <div className="flex items-center ...">...</div>
)}
```

Default: `'0'` → invisible en producción y demo. Para desarrollo local se agrega `VITE_DEV_TOOLS=1` al `.env.local` (no commitear).

**Alternativa descartada**: `import.meta.env.DEV` (modo Vite dev). No sirve porque el ScreenNavigator debe estar disponible en modo `preview` para presentaciones, pero no en `build` de producción. El flag explícito da control granular.

**Alternativa descartada**: feature flag en backend. Sobreingeniería para algo que es puramente presentacional y de entorno.

### D-5: Limpieza de strings — inventario y reformulaciones

| Archivo | Línea | Original | Reformulado | Acción |
|---------|-------|----------|-------------|--------|
| `StudentProfile.tsx` | ~595 | `"Control de demostración"` | eliminado junto al bloque (oculto por `DEV_TOOLS_ENABLED`) | ocultar |
| `StudentProfile.tsx` | ~602 | `"Demo: simular deriva embedding"` | idem | ocultar |
| `StudentProfile.tsx` | ~688 | `"Disponible próximamente"` | `"No disponible en esta versión"` (más neutro) | reformular |
| `EnrollmentDniStep.tsx` | ~134 | `"Datos extraídos por OCR (demo)"` | `"Datos extraídos por OCR"` | reformular |
| `EnrollmentDniStep.tsx` | ~205 | `"Análisis indicativo (demo)"` | `"Análisis indicativo"` (el disclaimer L2.5 en el body se conserva íntegro) | reformular encabezado |
| `EquipmentCheck.tsx` | ~107 | `"(modo demo)"` en mensaje de fallas | quitar el sufijo; el mensaje queda: `"{fallas} requisito(s) con observaciones — podés continuar"` | reformular |
| `ScreenNavigator.tsx` | ~70 | `title="Navegador de pantallas (demo)"` | `title="Navegador de pantallas"` | reformular atributo |
| `ScreenNavigator.tsx` | ~79 | `api.modoDemo ? 'Modo demo' : 'Backend real'` | `api.modoDemo ? 'Modo simulación' : 'Backend real'` | reformular |
| `AdminDetectionHarness.tsx` | ~863 | `"Las señales de visión siguen siendo del stub"` | `"Las señales de visión corresponden al motor de respaldo (sin MediaPipe)"` | reformular |
| `ConfigureExam.tsx` | ~41 | `placeholder="Ej: Examen Final — Anatomía I"` | `placeholder="Nombre del examen"` | reformular |
| `ConfigureExam.tsx` | ~46 | `placeholder="Ej: Cátedra B"` | `placeholder="Nombre de la cátedra"` | reformular |

**Invariantes L2.5 que NO se tocan**:
- El body del disclaimer en EnrollmentDniStep (~206-216): "Este resultado es preliminar y orientativo... La validación oficial del documento... se realiza server-side... El cliente es un sensor no confiable... La decisión de habilitación o sanción es siempre humana — el sistema no aprueba ni rechaza automáticamente (L2.5)."
- Texto en StudentProfile sobre Ley 25.326 y dato sensible.
- Texto en AuditPrivacy sobre DPIA y retención.

### D-6: Corrección de stacks de botones sin gap

En `AdminDashboard.tsx` el bloque "Acciones rápidas" tiene tres `<Button className="w-full">` consecutivos sin separación. Se agrega `space-y-sm` al contenedor (o se migra a `flex flex-col gap-sm`). Se hace un pase equivalente en cualquier otro stack `w-full` sin gap detectado en el codebase (Proctor, AuditPrivacy si aplica).

## Risks / Trade-offs

- **[Riesgo] Regresión de tamaños Button**: al agregar `size`, cualquier uso que hoy pase `className="h-9 ..."` para sobreescribir el tamaño puede generar conflicto de clases Tailwind. → Mitigation: el pase de limpieza de jerga también audita todos los usos de `<Button` y migra overrides de tamaño a la prop `size`.
- **[Riesgo] DEV_TOOLS_ENABLED no definido en entornos CI**: si la variable no está definida, `import.meta.env.VITE_DEV_TOOLS` es `undefined`, que `=== '1'` evalúa `false` → comportamiento correcto (herramientas ocultas). Sin riesgo real.
- **[Trade-off] FormField/RangeInput en components.tsx vs. archivo propio**: se agregan a `components.tsx` para no fragmentar el barrel de UI. Si el archivo crece, se puede extraer en un `change` de refactor posterior.
- **[Riesgo] Disclaimer L2.5 mutilado**: al quitar "(demo)" del encabezado de EnrollmentDniStep, alguien podría pensar que el análisis es "oficial". → Mitigation: el body del disclaimer se conserva íntegro (ver D-5); solo se limpia el encabezado `<p>` que actúa como título de sección.

## Open Questions

- ¿Se debe agregar `VITE_DEV_TOOLS=1` al `.env.example` del repo para que los nuevos devs lo encuentren, o solo documentarlo en un comentario? → Preferencia: `.env.example` con valor `0` y comentario explicativo (no es secreto).
- ¿Los botones de AuditPrivacy y Proctor tienen stacks sin gap que requieran corrección en este change, o se delegan al change de rediseño de esas pantallas? → Decisión: si el problema es visible en el estado actual (botones pegados), se corrige aquí; si el layout está bien con el diseño actual, se pospone.
