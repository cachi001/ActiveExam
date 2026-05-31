## Why

Hoy el alumno, tras el login, aterriza directamente en `/requisitos` sin ningún contexto sobre qué examen va a rendir ni si tiene inscripciones activas. El modelo de datos mock no tiene entidades `Materia`, `Comision` ni `Inscripcion` (solo `catedra: string` en `Examen`), lo que impide representar la jerarquía real de la academia (materia → comisión → examen) y ofrece al alumno una experiencia pobre que no refleja el flujo institucional de UTN FRM. Este change introduce el portal del alumno completo en la demo (dashboard, navegación de materias/comisiones, inscripción a exámenes y perfil personal) sin tocar el backend real.

## What Changes

- **Landing del alumno**: tras login con rol `estudiante`, la aplicación redirige a `/alumno/dashboard` en lugar de `/requisitos`.
- **Modelo mock extendido**: se agregan tipos `Materia`, `Comision`, `Inscripcion` en `lib/types.ts` y datos de demo de UTN FRM (cátedras de ingeniería, emails `@frm.utn.edu.ar`).
- **API mock nueva** en `lib/api.ts`: `materiasDisponibles()`, `comisionesDeMateria(materiaId)`, `examenesDeComision(comisionId)`, `inscribir(examenId)`, `misInscripciones()`, `puedeRendir()`.
- **Pantalla dashboard del alumno** (`screens/AlumnoDashboard.tsx`): resumen de materias cursando, próximos exámenes e inscripciones activas.
- **Pantalla exploración materia/comisión** (`screens/AlumnoMaterias.tsx`): lista de materias disponibles → detalle de comisiones → lista de exámenes con botón "Inscribirme".
- **Pantalla "Mis exámenes"** (`screens/AlumnoMisExamenes.tsx`): inscripciones del alumno con estado (`inscripto` / `pendiente` / `habilitado` / `rendido`) y acción siguiente (rendir / completar perfil / ver resultado).
- **Pantalla perfil del alumno** (`screens/AlumnoPerfil.tsx`): datos personales + secciones `consentimiento` y `verificacion_biometrica` como contenedores con estado de completitud (placeholder; el contenido real es de C-22).
- **Gate `puedeRendir`**: si perfil incompleto, redirige a completar perfil en lugar de iniciar `/requisitos`.
- **Rutas nuevas**: `/alumno/dashboard`, `/alumno/materias`, `/alumno/mis-examenes`, `/alumno/perfil` en `lib/router.tsx`.
- **ScreenNavigator actualizado**: grupo "Estudiante" incluye las nuevas pantallas.
- **Rebrand UTN FRM**: datos demo con nombres, cátedras y emails de UTN Regional Mendoza. Se eliminan referencias a UBA en los datos nuevos.

## Capabilities

### New Capabilities

- `student-dashboard-landing`: landing del alumno post-login; resumen de actividad académica y navegación al portal.
- `student-portal-navigation`: exploración jerárquica materia → comisión → examen con tipos mock y API mock.
- `exam-enrollment`: inscripción del alumno a un examen y registro de inscripciones con estado y acción siguiente.
- `student-profile-shell`: pantalla de perfil con datos personales y contenedores de consentimiento y biometría (estado de completitud + gate `puedeRendir`).

### Modified Capabilities

_(ninguna — este change no altera requisitos de specs existentes; solo agrega capas nuevas en el frontend de demo)_

## Impact

- `frontend/src/lib/types.ts` — tipos nuevos: `Materia`, `Comision`, `Inscripcion`, `EstadoInscripcion`.
- `frontend/src/lib/api.ts` — datos demo UTN FRM; métodos nuevos del API mock; rebrand de `PRINCIPALES.estudiante`.
- `frontend/src/lib/router.tsx` — rutas `/alumno/*` nuevas.
- `frontend/src/ui/ScreenNavigator.tsx` — grupo Estudiante ampliado.
- `frontend/src/screens/` — cuatro pantallas nuevas: `AlumnoDashboard.tsx`, `AlumnoMaterias.tsx`, `AlumnoMisExamenes.tsx`, `AlumnoPerfil.tsx`.
- `frontend/src/App.tsx` (o punto de montaje del router) — mapeo de rutas nuevas.
- Sin cambios en backend, base de datos ni specs de capabilities existentes.
