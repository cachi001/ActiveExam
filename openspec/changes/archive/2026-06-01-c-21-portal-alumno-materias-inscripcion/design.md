## Context

El frontend de demo de ActiveExam (React + Vite + Zustand + Tailwind) tiene hoy un flujo de estudiante lineal: login → `/requisitos` → consentimiento → biometría → sala-espera → examen → cierre. No existe ninguna pantalla de portal, ni entidades `Materia`/`Comision`/`Inscripcion` en el mock. El único vínculo alumno-examen es el campo `catedra: string` en `Examen`. El change opera exclusivamente en la capa demo/mock del frontend sin tocar el backend real ni el pipeline de visión.

## Goals / Non-Goals

**Goals:**
- Modelar la jerarquía Materia → Comisión → Examen en el mock (tipos + datos).
- Introducir un dashboard de aterrizaje post-login para el rol `estudiante`.
- Permitir navegar materias y comisiones, ver exámenes disponibles e inscribirse.
- Mostrar "Mis exámenes" con estado de inscripción y acción siguiente.
- Proveer una pantalla de perfil del alumno con contenedores de consentimiento y biometría (shell) y un gate `puedeRendir` que bloquea el inicio del examen si el perfil está incompleto.
- Rebrandear los datos demo a UTN FRM (cátedras de ingeniería, `@frm.utn.edu.ar`).

**Non-Goals:**
- Implementar el contenido de consentimiento ni el escaneo biométrico (pertenecen a C-22).
- Conectar con el backend real.
- Alterar el pipeline de visión, eventos, proctor, revisor o admin.
- Cambiar el flujo post-inscripción (requisitos → examen) — ese flujo existente se preserva, solo se añade el entry point correcto.

## Decisions

### Decisión 1 — Jerarquía de tipos: Materia → Comision → Examen

**Elegido**: agregar `Materia` y `Comision` como tipos nuevos en `lib/types.ts`; `Examen` existente se mantiene intacto y se asocia a `Comision` via `comision_id`. Los datos demo de `EXAMENES` existentes se mapean a comisiones UTN FRM.

**Alternativa descartada**: reemplazar `Examen.catedra` por `materia_id` + `comision_id`. Descartada porque rompería el resto de pantallas (proctor, revisor, admin) que usan `catedra` directamente. La estrategia de extensión no destructiva es más segura en el contexto demo.

### Decisión 2 — API mock: métodos independientes por entidad

**Elegido**: añadir métodos discretos al objeto `api` existente: `materiasDisponibles()`, `comisionesDeMateria(id)`, `examenesDeComision(id)`, `inscribir(examenId)`, `misInscripciones()`, `puedeRendir()`. Los datos viven en constantes top-level en `api.ts`.

**Alternativa descartada**: crear un módulo `api-alumno.ts` separado. Descartada porque fragmenta la superficie de mock y rompe el patrón establecido de un solo objeto `api` exportado.

### Decisión 3 — Gate `puedeRendir` modelado en el mock

**Elegido**: `puedeRendir()` devuelve `{ puede: boolean; razon?: string }`. El campo `perfil_alumno.consentimiento_ok` y `perfil_alumno.biometria_ok` son flags booleanos en el estado in-memory. Inicialmente ambos en `false` (perfil incompleto). El alumno puede simularlos desde la pantalla de perfil con un botón de demo "Marcar como completado".

**Rationale**: permite demostrar el gate sin implementar el flujo real (que es de C-22). El botón de demo lleva un label explícito "Demo: simular completado" para evitar confusión.

### Decisión 4 — Rutas `/alumno/*` como namespace

**Elegido**: todas las pantallas del portal del alumno viven bajo `/alumno/`: `/alumno/dashboard`, `/alumno/materias`, `/alumno/mis-examenes`, `/alumno/perfil`. El router hash existente (matching exacto) soporta esto sin cambios estructurales.

**Alternativa descartada**: rutas planas (`/dashboard`, `/materias`). Descartada porque colisionan con potenciales rutas de otros roles y no expresan claramente el contexto del rol.

### Decisión 5 — Rebrand UTN FRM solo en datos nuevos

**Elegido**: los datos mock nuevos (materias, comisiones, `PRINCIPALES.estudiante`) usan UTN FRM (`@frm.utn.edu.ar`, cátedras de ingeniería). Los datos de sesiones vivas / cola de revisión (que otros roles usan) no se tocan para no romper demos existentes.

### Decisión 6 — Shell de perfil: contenedores con estado de completitud

**Elegido**: `AlumnoPerfil.tsx` renderiza dos tarjetas: "Consentimiento informado" y "Verificación biométrica". Cada una muestra el estado (`completado` / `pendiente`) y un botón de demo para simular completitud. El contenido real (bloque de texto de consentimiento, captura de foto) es placeholder de C-22.

## Risks / Trade-offs

| Riesgo | Mitigación |
|--------|-----------|
| Los datos demo UTN FRM en `EXAMENES` (reutilizados por proctor/revisor) podrían quedar inconsistentes con el rebrand parcial. | Solo se rebrandan los datos nuevos (materias, comisiones, `PRINCIPALES.estudiante`). Los exámenes existentes conservan sus IDs para no romper la demo de otros roles. |
| El gate `puedeRendir` depende de estado en memoria; un reload lo resetea. | Aceptable en la demo. C-22 implementará persistencia real. Se documenta en la UI con un aviso. |
| Cuatro pantallas nuevas agregan peso al bundle inicial. | El objetivo `< 500 KB` aplica al bundle inicial de producción; en modo demo, Vite sirve en dev. Las pantallas nuevas son ligeras (sin dependencias externas adicionales). |
| `Routes` en el router usa matching exacto — rutas con parámetros dinámicos (e.g., `/alumno/materias/:id`) no son soportadas nativamente. | Las pantallas de detalle reciben el `id` a través del store Zustand (patrón ya establecido en la app, e.g., `/revisor/detalle`), no via URL params. |

## Migration Plan

1. Agregar tipos en `lib/types.ts` (no destructivo).
2. Agregar datos y métodos mock en `lib/api.ts` (no destructivo).
3. Crear cuatro pantallas nuevas en `screens/`.
4. Registrar rutas en `App.tsx` (o donde se monte el router).
5. Actualizar `ScreenNavigator.tsx`.
6. Cambiar el destino de `navigate` post-login en `screens/Login.tsx` de `/requisitos` a `/alumno/dashboard`.

Rollback: revertir el cambio en `Login.tsx` y eliminar las rutas `/alumno/*`. Los demás cambios son aditivos y no afectan los flujos existentes.

## Open Questions

- ¿El alumno puede estar inscripto a más de un examen activo simultáneamente? Para la demo se asume que sí; se muestra el listado completo. La restricción real es de dominio y queda para el backend.
- ¿La foto de referencia del alumno en el perfil viene de la institución o se captura en el flujo biométrico? C-22 lo resuelve; el shell de C-21 muestra un placeholder.
