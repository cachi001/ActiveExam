## Context

El frontend (React 18 + Vite + Zustand + Tailwind) tiene 19 menciones de "L2.5", 4 de "embedding", y varias de "WORM", "liveness", "cadena de custodia" y "Face Mesh" dispersas en ~16 archivos. Ningún término está explicado. El usuario (alumno, admin, revisor) los ve en pantallas críticas: pantalla de consentimiento, acuse por examen, perfil biométrico, panel de revisión.

Contexto técnico relevante:
- Ya existe `frontend/src/config/institution.ts` (creado en C-27) como módulo TypeScript puro, export named, sin reactividad, sin context provider. C-28 sigue el **mismo patrón** para `glossary.ts`.
- Ya existen primitivas UI en `frontend/src/ui/components.tsx` (Icon, Button, Card, Badge, etc.) y shells en `frontend/src/ui/shells.tsx`. El nuevo `<Term>` va en `frontend/src/ui/Term.tsx` (archivo propio, no en components.tsx) para no inflarlo.
- La terminología técnica NO debe eliminarse — es necesaria legal y técnicamente. El objetivo es **envolverla** con una explicación accesible en contexto.
- Sin backend involucrado: 100 % capa de presentación. Sin nuevas rutas de API, sin cambios de BD.

Términos a definir (7 entradas en el glosario):

| Término | Definición en lenguaje claro |
|---------|------------------------------|
| L2.5 | Nivel de supervisión donde el sistema **nunca sanciona automáticamente**: solo prioriza casos para revisión. La decisión disciplinaria la toma **siempre una persona**. |
| embedding | Representación numérica de la geometría de tu rostro. Se trata como **dato sensible** (Ley 25.326) y se elimina al egreso. No es una foto. |
| WORM | Almacenamiento "Write Once Read Many": una vez escrito, el archivo **no puede modificarse ni borrarse**. Garantiza que la evidencia es auténtica. |
| liveness | Prueba de que hay una **persona viva** frente a la cámara (no una foto, video ni máscara). Parte de la verificación de identidad. |
| cadena de custodia | Registro criptográfico que **prueba que la evidencia no fue alterada** desde su captura hasta la revisión. Cada paso queda firmado. |
| Face Mesh | Malla de 468 puntos del rostro generada por la biblioteca MediaPipe para medir geometría facial. Insumo del embedding. |
| datos biométricos | Datos obtenidos de características físicas (aquí: geometría facial). Clasificados como **datos sensibles** bajo Ley 25.326; requieren consentimiento informado explícito. |

## Goals / Non-Goals

**Goals:**
- Diccionario central único: `frontend/src/config/glossary.ts` (mismo patrón que `institution.ts`).
- Componente átomo `<Term>` en `frontend/src/ui/Term.tsx`: accesible (aria-describedby / role="tooltip"), responsive (funciona en touch/mobile con tap), sin dependencias externas.
- Reemplazar las menciones crudas más visibles para el alumno con `<Term>` (L2.5 en todas las pantallas del alumno; embedding y WORM en las pantallas de consentimiento; liveness en la pantalla biométrica; cadena de custodia en Revisor, SessionDetail, Examen).
- Vista opcional de glosario completo `<GlossaryPanel>` (modal) accesible desde el footer o desde un icono "?" en pantallas clave.

**Non-Goals:**
- Eliminar la terminología técnica (es necesaria legal y técnicamente).
- Reemplazar menciones internas de código, comentarios de desarrollador ni `api.ts` (el L2.5 en api.ts es un comentario de dev, no texto de usuario).
- Backend, contratos de API, BD, tests de integración.
- Internacionalización (i18n) del glosario — fuera de scope del MVP.
- Animaciones complejas ni librerías de tooltip externas (Tailwind puro o clases CSS propias).

## Decisions

### D-01: Módulo `frontend/src/config/glossary.ts` — mismo patrón que `institution.ts`

**Decisión**: Módulo TypeScript puro, export named `GLOSSARY: Record<TermKey, GlossaryEntry>`, sin reactividad, sin context provider. Import directo en los componentes.

**Alternativas consideradas**:
- **A) Inline en cada componente**: descartado — es exactamente el problema actual (dispersión).
- **B) Zustand store**: descartado — el glosario es configuración estática, no estado reactivo.
- **C) JSON en `public/`**: descartado — fetch asíncrono innecesario para datos estáticos.
- **D) Módulo TS puro** (elegido): mismo patrón que `institution.ts`, tree-shakeable, tipado, import directo.

**Forma del contrato**:
```typescript
export type TermKey =
  | 'l2_5'
  | 'embedding'
  | 'worm'
  | 'liveness'
  | 'cadena_de_custodia'
  | 'face_mesh'
  | 'datos_biometricos';

export interface GlossaryEntry {
  /** Texto del término tal como aparece en la UI (ej. "L2.5") */
  label: string;
  /** Definición en lenguaje claro, máx. 2 frases */
  definition: string;
  /** Referencia legal opcional (ej. "Ley 25.326, Art. 2") */
  legalRef?: string;
}

export const GLOSSARY: Record<TermKey, GlossaryEntry> = { ... };
```

### D-02: Componente `<Term>` en `frontend/src/ui/Term.tsx` — archivo propio

**Decisión**: Componente átomo en archivo separado (`Term.tsx`), no agregado a `components.tsx`. Motivo: `components.tsx` ya tiene primitivas genéricas; `<Term>` es específico del dominio del glosario y tiene lógica de tooltip.

**API del componente**:
```tsx
interface TermProps {
  termKey: TermKey;          // clave en GLOSSARY
  children?: React.ReactNode; // texto visible; si se omite, usa GLOSSARY[key].label
  className?: string;
}
```

**Implementación del tooltip**:
- **Desktop (hover)**: CSS puro con Tailwind (`group`, `group-hover:visible`, `group-hover:opacity-100`). Sin JS para mostrar/ocultar — sin dependencias externas.
- **Mobile (tap)**: estado local `useState<boolean>` para `isTipVisible`; `onClick` toggle; `onBlur`/click fuera para cerrar. El tooltip es un `<div role="tooltip" id={id} aria-describedby={id}>`.
- **Accesibilidad**: el texto técnico tiene `aria-describedby` apuntando al tooltip; el icono "?" tiene `aria-label="Ver definición de {label}"`.
- **Visual**: texto subrayado con puntos (`underline decoration-dotted cursor-help`) + icono pequeño "?" al lado.

**¿Por qué sin librería externa?**: Tailwind + estado local alcanza para el caso de uso; añadir @radix-ui/react-tooltip o Floating UI sería sobre-ingeniería para tooltips estáticos. Si escala a casos más complejos (posicionamiento dinámico, animaciones), se puede migrar entonces.

### D-03: `<GlossaryPanel>` — modal con lista completa

**Decisión**: Componente separado `frontend/src/ui/GlossaryPanel.tsx`. Modal simple (no una ruta nueva) que itera `Object.values(GLOSSARY)` y muestra cada término con su definición y referencia legal. Activado por un botón "Glosario" en el footer de la shell (`shells.tsx`) y opcionalmente desde un icono "?" en pantallas de consentimiento/acuse.

**Alternativa descartada — ruta dedicada `/glosario`**: añadir una ruta requeriría tocar el router y la nav. Un modal es más ligero y no necesita URL propia para este caso.

### D-04: Orden de reemplazo de menciones — prioridad por impacto al alumno

Prioridad 1 (alumno — pantallas que el alumno ve directamente):
- L2.5: AcuseExamen, Cierre, EnrollmentBiometricStep, StudentProfile
- embedding: ConsentScreen, Consent, EnrollmentConsentStep, StudentProfile
- WORM: ConsentScreen
- liveness: Biometria, EnrollmentBiometricStep

Prioridad 2 (admin/revisor):
- L2.5: AdminDashboard, Reports, Revisor, AdminDetectionHarness, BiometricRenewalStatus
- cadena de custodia: Revisor, SessionDetail, Examen

Prioridad 3 (opcional):
- Face Mesh: si aparece como texto visible al usuario (verificar en implementación)

### D-05: `api.ts:318` — NO reemplazar

La mención de "L2.5" en `api.ts:318` es un comentario de desarrollador o campo de datos internos, no texto de UI visible al usuario. No se envuelve con `<Term>`. Confirmar en implementación.

## Risks / Trade-offs

- **[Riesgo] Tooltip clipeado en contenedores con overflow:hidden** → Mitigación: usar `overflow-visible` en el contenedor padre del tooltip o portar a portal (`ReactDOM.createPortal`) si el clipping es problema real. Detectar en implementación.
- **[Riesgo] Mobile: el tap en `<Term>` compite con el tap en el elemento padre** → Mitigación: `stopPropagation` en el onClick del tooltip; `onBlur` para cierre.
- **[Trade-off] Tooltip CSS puro vs. librería**: CSS puro con Tailwind es más simple pero no maneja posicionamiento dinámico (flip en bordes de pantalla). Aceptable para el MVP; si hay quejas de UX se migra.
- **[Riesgo] Dispersión incompleta** → Hay 16 archivos a modificar; es fácil olvidar uno. Las tasks deben listar cada archivo y mención explícitamente para que el agente de implementación no las omita.
- **[Trade-off] Definiciones en español en el código fuente**: las definiciones están hardcodeadas en español en `glossary.ts`. Si el proyecto requiere i18n en el futuro, habrá que refactorizar. Aceptable para MVP mono-idioma.

## Migration Plan

1. Crear `frontend/src/config/glossary.ts` con el tipo `TermKey`, la interfaz `GlossaryEntry` y el objeto `GLOSSARY` con las 7 entradas.
2. Crear `frontend/src/ui/Term.tsx` con la lógica de tooltip (CSS Tailwind + estado local para mobile).
3. Crear `frontend/src/ui/GlossaryPanel.tsx` con el modal de lista completa.
4. Agregar botón "Glosario" en `frontend/src/ui/shells.tsx` (footer).
5. Reemplazar menciones en archivos de Prioridad 1 (alumno) — 8 archivos.
6. Reemplazar menciones en archivos de Prioridad 2 (admin/revisor) — 5 archivos.
7. Verificar visualmente en el navegador: tooltip aparece, es legible, funciona en mobile.

**Rollback**: revertir los cambios; no hay cambios de BD ni API. `glossary.ts` y `Term.tsx` pueden borrarse sin efecto secundario si nadie los importa.

## Open Questions

- **¿Existe `frontend/src/ui/GlossaryPanel.tsx` ya?** Verificar antes de crearlo.
- **¿`api.ts:318` muestra "L2.5" en la UI o es solo metadata interna?** Confirmar al implementar; si es solo un campo de datos que el usuario nunca lee directamente, no envolverlo con `<Term>`.
- **¿El tooltip en `<Term>` necesita posicionamiento dinámico (flip al borde de pantalla)?** Si sí, evaluar `@floating-ui/react` como dependencia. Empezar con CSS puro y ajustar si hay reporte de UX.
- **¿Se agrega `<GlossaryPanel>` a la nav del alumno o solo al footer?** Decision: footer primero; si el producto lo pide, se agrega a la nav en un change posterior.
