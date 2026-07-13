## Why

Hoy un alumno **ve y puede rendir CUALQUIER examen del catálogo sin estar inscripto** a su materia/comisión. Es un agujero de control de acceso, verificado en prod:

- `listar_examenes_contenido` (exam_content/router.py:1266) devuelve **todos** los exámenes del catálogo — *"Cualquier principal autenticado puede consultar el catálogo"* — **sin filtrar por inscripción**.
- El gate `puede_rendir` (inscripcion_service.py:251) es `consentimiento_vigente AND biometria_vigente` — **la inscripción NO participa**. El propio código lo admite: la auto-matrícula *"No altera el gate puede_rendir (solo set-membership)"* (router.py:1309).
- `crear_sesion` (proctoring/sessions) valida ventana + intentos, pero **no** inscripción.

Resultado: la inscripción por código (C-70) es hoy **decorativa** — no restringe nada. La tabla `inscripcion` en prod tiene 0 filas y aun así los alumnos ven el examen demo.

> **Alcance de C-71**: este change agrupa el trabajo que influye en el flujo de examen. Se implementa por slices: **(1) gate de inscripción** (este documento, se arranca ahora), **(2) Cola de Revisión** (funcionalidad + mejora de la página) y **(3) Sesiones Grabadas**. Los slices 2 y 3 se especifican (specs/tasks) al encararlos; este proposal detalla el slice 1.

## What Changes

- **La inscripción pasa a ser condición de acceso, no adorno.** El alumno solo ve y solo puede rendir exámenes de las materias/comisiones **donde está inscripto por código**.
- **Materias/comisiones filtradas por inscripción**: la pantalla "Mis materias" muestra **únicamente** las comisiones donde el alumno se matriculó (por código). Sin inscripción → no aparece ninguna materia.
- **Exámenes filtrados por inscripción**: "Exámenes disponibles" muestra solo los exámenes de las comisiones inscriptas. Sin inscripción a esa comisión → el examen **no aparece**.
- **Gate de rendición DOBLE y server-side**: rendir un examen exige **AMBAS** condiciones — (1) perfil completo **Y** (2) inscripto en la materia+comisión de ese examen. Si falta cualquiera, no se habilita. **BREAKING**: hoy alcanza solo con el perfil.
- **Backstop server-side en `crear_sesion`**: además del filtrado del catálogo (frontend), el backend rechaza crear la sesión si el alumno no está inscripto en la comisión del examen (cliente = sensor no confiable, regla dura #6).
- **Nada hardcodeado**: todo sale de la DB real (`inscripcion` por `usuario_id`), no de arrays mock ni catálogos fijos.

## Capabilities

### New Capabilities
- `enrollment-render-gate`: la inscripción a la materia+comisión es precondición (junto con el perfil completo) para ver y rendir un examen; enforced server-side.

### Modified Capabilities
- `exam-enrollment`: el gate `puedeRendir` deja de exigir solo el perfil y pasa a exigir **perfil completo Y inscripción** a la materia+comisión del examen.

## Impact

- **Backend (slim = prod)**:
  - `listar_examenes_contenido`: filtrar por las comisiones inscriptas del principal (JOIN con `inscripcion` por `usuario_id`); admin conserva la vista completa.
  - Endpoint/consulta "mis materias/comisiones": derivar de `inscripcion` del alumno (no de todas las comisiones).
  - `puede_rendir` / `InscripcionService`: agregar la condición `inscripto_en(comisión_del_examen)` al gate (además de perfil).
  - `crear_sesion` (proctoring/sessions/router.py): backstop server-side — 403 si el alumno no está inscripto en la comisión del `examen_contenido`.
- **Frontend**: `misMaterias`/`listarExamenesContenido`/`puedeRendir` consumen el resultado ya filtrado; Mis Materias y Mis Exámenes muestran vacío coherente cuando no hay inscripción (CTA a matricularse por código).
- **Datos**: sin migración (usa `inscripcion` existente, C-70). Reusa la FK `examen_contenido.comision_id`.
- **Gobernanza**: control de acceso a exámenes = dominio sensible. Tests sin mocks de DB (regla #4), Pydantic `extra='forbid'` (#5), snake_case (#6), sin hardcodes.
