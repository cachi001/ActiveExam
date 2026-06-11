---
name: help-system-content
description: >
  Patrón para agregar botones de ayuda contextual (HelpButton) a las pantallas y
  formularios de la web, con contenido escrito en lenguaje claro para una persona
  que NO entiende de tecnología. Genérico: no depende de ningún look-and-feel
  concreto; se apoya en el HelpButton y los tokens de diseño del propio proyecto.
  Trigger: al crear una pantalla nueva, al agregar un formulario de crear/editar,
  o al revisar/redactar el texto de un botón de ayuda.
license: Apache-2.0
metadata:
  author: gentleman-programming
  adapted-for: ActiveExam (proctoring web)
  version: "2.0"
---

## Cuándo usar esta skill

- Creás una pantalla nueva (cualquier vista con su propio header/título).
- Agregás un formulario de crear/editar (modal o sección de form).
- Revisás o redactás el texto de un botón de ayuda existente.
- Cualquier pantalla de cara al usuario que NO tenga su `HelpButton`.

---

## La regla de oro: el contenido es para un HUMANO que NO entiende

Esto es lo más importante de toda la skill. El texto de ayuda lo lee un usuario final
—un alumno, un docente, un revisor—, **no un programador**. Si la persona necesita
saber qué es una variable, un componente o un umbral para entender la ayuda, la ayuda
está mal escrita.

**SÍ:** describí qué ve la persona en la pantalla y qué puede hacer, en sus palabras.
**NO:** nombres de variables, props, estados internos, nombres de componentes, rutas de
archivos, valores técnicos crudos, ni jerga del dominio sin traducir.

| ❌ NO escribir (jerga técnica) | ✅ SÍ escribir (lenguaje humano) |
|--------------------------------|----------------------------------|
| "El `score` supera el `threshold` configurado" | "La sesión quedó marcada como prioritaria para revisar" |
| "Se persiste el `embedding` de referencia" | "Guardamos tu foto de referencia para confirmar tu identidad" |
| "Estado `IN_PROGRESS` del `ProctoringSession`" | "El examen está en curso" |
| "Llama al endpoint `POST /verify-chain`" | "Generás un certificado para auditoría externa" |
| "Toggle del detector `gaze`" | "Activás o desactivás el control de la mirada" |

Si una palabra del dominio es inevitable (ej. "proctoring", "liveness"), **explicala en
la misma frase la primera vez** o usá el glosario del proyecto (`Term` / `GlossaryPanel`).

---

## El componente en este proyecto

Ya existe y está adoptado: **`frontend/src/ui/HelpButton.tsx`**. NO crear uno nuevo ni
copiar el de otro proyecto.

```tsx
import { HelpButton } from '../ui/HelpButton';

<HelpButton title="Supervisión en vivo">
  {/* contenido JSX libre: <p>, <ul>, <strong>, <em> */}
</HelpButton>
```

API:
- `title: string` — título grande del modal, en lenguaje humano (ej. "Supervisión en vivo").
- `children: ReactNode` — el contenido explicativo (JSX inline; **no hay** un archivo central
  de contenidos, va en la propia pantalla/formulario).
- `ariaLabel?: string` — tooltip del botón (defecto "Ayuda de esta página").
- `className?: string` — para alinear el botón en distintos headers.

Características que ya resuelve el componente (no reimplementar): modal accesible
(`role="dialog"`, Esc cierra, click afuera cierra), portal al `body`, bloqueo de scroll,
foco e íconos. Usa los **tokens de diseño del proyecto** (`surface-container`, `on-surface`,
`primary`, `outline-variant`, espaciados `px-lg`/`py-md`, tipografías `text-title-md`/
`text-body-md`). **No hardcodees colores** (`bg-zinc-800`, `text-orange-400`, etc.): si
necesitás resaltar, usá los tokens del proyecto o simplemente `<strong>`/`<em>`.

---

## Dónde va la ayuda

### Regla 1 — Toda pantalla tiene su HelpButton

Cada pantalla de cara al usuario pasa su `HelpButton` al header del shell, vía la prop de
ayuda del contenedor de página (`help={<HelpButton .../>}`). Sin excepción.

```tsx
<PageShell
  title="Panel de administración"
  subtitle="..."
  help={
    <HelpButton title="Panel de administración">
      <p>Qué es esta pantalla, en una frase.</p>
      <p>Qué puede hacer la persona desde acá.</p>
    </HelpButton>
  }
>
```

### Regla 2 — Todo formulario de crear/editar lleva su ayuda

Cada formulario de crear/editar incluye un `HelpButton` arriba del form que explica
**para qué sirven los campos en palabras simples** (qué poner, qué es obligatorio, qué pasa
al guardar). Esta ayuda describe el formulario, va inline en el componente del form.

```tsx
<div className="flex items-center gap-sm mb-sm">
  <HelpButton title="Configurar examen">
    <p><strong>Completá estos datos</strong> para preparar el examen:</p>
    <ul className="list-disc pl-5 space-y-1">
      <li><strong>Nombre:</strong> Cómo van a ver el examen los alumnos. Es obligatorio.</li>
      <li><strong>Duración:</strong> Cuántos minutos tienen para resolverlo.</li>
    </ul>
  </HelpButton>
  <span className="text-body-sm text-on-surface-variant">Ayuda sobre este formulario</span>
</div>
```

---

## Estructura del contenido (genérica, agnóstica del diseño)

Todo contenido de ayuda sigue el mismo orden, de lo simple a lo detallado:

1. **Intro de una frase** — para qué sirve esta pantalla / este formulario.
2. **Qué ves y qué podés hacer** — lista corta de acciones, cada una con un `<strong>` y una
   explicación en una línea.
3. **Aclaración o advertencia (opcional)** — un dato útil ("primero seleccioná X"), o una
   advertencia si la acción es irreversible (ej. "esto no se puede deshacer").

```tsx
<HelpButton title="Materias">
  <p>Acá ves las materias en las que estás inscripto este cuatrimestre.</p>
  <ul className="list-disc pl-5 space-y-1">
    <li><strong>Ver exámenes:</strong> Entrás a una materia para ver sus exámenes próximos.</li>
    <li><strong>Inscribirte:</strong> Sumás una materia nueva desde el buscador.</li>
  </ul>
  <p><em>Si no ves una materia, fijate que ya esté habilitada por tu facultad.</em></p>
</HelpButton>
```

Para una advertencia (acción irreversible), no hardcodees una paleta: usá un `<strong>`
claro y, si querés un recuadro, los tokens del proyecto (ej. `bg-error-container
text-on-error-container`), nunca colores crudos de otro proyecto.

---

## Tono

- Idioma: **español rioplatense (voseo)** — "ves", "llegás", "seleccioná", "tené en cuenta".
  Es el tono que ya usa la web del proyecto.
- Estilo: instructivo y corto — "Hacé clic en X para Y".
- Cercano y profesional, **sin lenguaje de marketing** y sin tecnicismos.
- Cada ítem de lista: `<strong>Etiqueta:</strong> explicación de una línea`.

---

## Checklist al agregar ayuda a una pantalla nueva

1. Importá `HelpButton` desde `../ui/HelpButton` (ajustá la ruta relativa).
2. Pasá `help={<HelpButton title="...">...</HelpButton>}` al shell/contenedor de la página.
3. Escribí el contenido siguiendo la estructura: intro → qué ves/hacés → aclaración.
4. Releé el texto preguntándote: *"¿una persona que no sabe nada de tecnología entiende
   esto?"* Si hay un nombre de variable, un estado interno o un valor técnico crudo → reescribilo.
5. Si la pantalla tiene un formulario de crear/editar, agregale su propio `HelpButton`
   inline que explique los campos.

---

## Referencias en este repo

- **Componente**: `frontend/src/ui/HelpButton.tsx` (ya existe, no recrear).
- **Glosario para términos del dominio**: `frontend/src/ui/Term.tsx` + `GlossaryPanel.tsx`
  + `frontend/src/config/glossary.ts`.
- **Ejemplos buenos ya escritos**: `screens/AdminDashboard.tsx`, `screens/Proctor.tsx`,
  `screens/AlumnoMaterias.tsx`, `screens/Reports.tsx` (mirá cómo describen en lenguaje claro).
