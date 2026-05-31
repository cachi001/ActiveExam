## 1. Tipos y modelo mock (lib/types.ts)

- [x] 1.1 Agregar tipo `EstadoInscripcion = 'inscripto' | 'pendiente' | 'habilitado' | 'rendido'` en `lib/types.ts`
- [x] 1.2 Agregar interfaz `Materia` con campos `id`, `nombre`, `codigo`, `descripcion` en `lib/types.ts`
- [x] 1.3 Agregar interfaz `Comision` con campos `id`, `materia_id`, `nombre`, `docente`, `horario` en `lib/types.ts`
- [x] 1.4 Agregar interfaz `Inscripcion` con campos `id`, `examen_id`, `comision_id`, `materia_id`, `nombre_examen`, `nombre_materia`, `fecha`, `estado: EstadoInscripcion` en `lib/types.ts`
- [x] 1.5 Verificar que `tsc --noEmit` pasa sin errores tras los cambios de tipos

## 2. Datos demo y API mock (lib/api.ts)

- [x] 2.1 Rebranding de `PRINCIPALES.estudiante`: cambiar `id_institucional` a formato UTN FRM, `email` a `@frm.utn.edu.ar`, `jurisdiccion` y nombre a contexto UTN Regional Mendoza
- [x] 2.2 Agregar constante `MATERIAS: Materia[]` con al menos 3 materias de ingeniería de UTN FRM (e.g., Análisis Matemático, Física I, Programación)
- [x] 2.3 Agregar constante `COMISIONES: Comision[]` con al menos 2 comisiones por materia, referenciando docentes con emails `@frm.utn.edu.ar`
- [x] 2.4 Asociar los exámenes existentes en `EXAMENES` a comisiones via `comision_id` (extensión no destructiva — no romper campos existentes como `catedra`)
- [x] 2.5 Agregar constante `MIS_INSCRIPCIONES: Inscripcion[]` mutable (let) con inscripciones demo en distintos estados
- [x] 2.6 Agregar estado de perfil in-memory: `let perfilAlumno = { consentimiento_ok: false, biometria_ok: false }`
- [x] 2.7 Implementar `api.materiasDisponibles(): Promise<Materia[]>` con delay simulado
- [x] 2.8 Implementar `api.comisionesDeMateria(materiaId: string): Promise<Comision[]>` con delay simulado
- [x] 2.9 Implementar `api.examenesDeComision(comisionId: string): Promise<Examen[]>` con delay simulado
- [x] 2.10 Implementar `api.inscribir(examenId: string): Promise<Inscripcion>` — crea o retorna inscripción existente, estado inicial `inscripto`
- [x] 2.11 Implementar `api.misInscripciones(): Promise<Inscripcion[]>` retornando `MIS_INSCRIPCIONES`
- [x] 2.12 Implementar `api.puedeRendir(): Promise<{ puede: boolean; razon?: string }>` — `puede: true` solo si `perfilAlumno.consentimiento_ok && perfilAlumno.biometria_ok`
- [x] 2.13 Implementar `api.simularConsentimientoOk()` y `api.simularBiometriaOk()` para los controles demo del perfil
- [x] 2.14 Verificar que `tsc --noEmit` pasa sin errores tras los cambios de API

## 3. Rutas (lib/router.tsx y App.tsx / punto de montaje)

- [x] 3.1 Registrar las rutas `/alumno/dashboard`, `/alumno/materias`, `/alumno/mis-examenes`, `/alumno/perfil` en el mapa de rutas del router
- [x] 3.2 Cambiar el `navigate` post-login en `screens/Login.tsx`: de `/requisitos` a `/alumno/dashboard`
- [x] 3.3 Verificar que `tsc --noEmit` pasa sin errores tras el cambio de rutas

## 4. Pantalla: AlumnoDashboard (student-dashboard-landing)

- [x] 4.1 Crear `frontend/src/screens/AlumnoDashboard.tsx` con: saludo personalizado, sección "Próximos exámenes" (lee `api.misInscripciones()` filtrado por estado `inscripto`/`habilitado`), banner de perfil incompleto si `puedeRendir().puede === false`, acceso rápido a Mis materias y Mis exámenes
- [x] 4.2 Verificar que la pantalla es navegable desde el ScreenNavigator sin errores de consola
- [x] 4.3 Verificar que `tsc --noEmit` pasa sin errores para este archivo

## 5. Pantalla: AlumnoMaterias (student-portal-navigation)

- [x] 5.1 Crear `frontend/src/screens/AlumnoMaterias.tsx` con: lista de materias (llama `api.materiasDisponibles()`), expansión de comisiones al seleccionar materia (llama `api.comisionesDeMateria(id)`), lista de exámenes al seleccionar comisión (llama `api.examenesDeComision(id)`)
- [x] 5.2 Mostrar botón "Inscribirme" solo para exámenes con estado `programado` sin inscripción activa del alumno; mostrar badge "Inscripto" si ya inscripto
- [x] 5.3 Al hacer clic en "Inscribirme", llamar `api.inscribir(examenId)` y actualizar la UI sin recargar la página
- [x] 5.4 Verificar que la pantalla es navegable desde el ScreenNavigator y que la inscripción demo funciona
- [x] 5.5 Verificar que `tsc --noEmit` pasa sin errores para este archivo

## 6. Pantalla: AlumnoMisExamenes (exam-enrollment)

- [x] 6.1 Crear `frontend/src/screens/AlumnoMisExamenes.tsx` con: lista de inscripciones (llama `api.misInscripciones()`), badge de estado por inscripción, acción "Rendir" si estado `habilitado` y `puedeRendir().puede === true`, acción "Completar perfil" si estado `habilitado` y `puedeRendir().puede === false`, mensaje de lista vacía con link a `/alumno/materias`
- [x] 6.2 Al hacer clic en "Rendir", verificar el gate `puedeRendir()` antes de navegar a `/requisitos`
- [x] 6.3 Verificar que con perfil incompleto, el botón "Rendir" no aparece y "Completar perfil" lleva a `/alumno/perfil`
- [x] 6.4 Verificar que `tsc --noEmit` pasa sin errores para este archivo

## 7. Pantalla: AlumnoPerfil (student-profile-shell)

- [x] 7.1 Crear `frontend/src/screens/AlumnoPerfil.tsx` con: sección de datos personales (nombre, legajo, email, institución), sección "Consentimiento informado" con badge de estado + control demo "Simular completado", sección "Verificación biométrica" con badge de estado + control demo "Simular completado"
- [x] 7.2 El control "Simular completado" llama a `api.simularConsentimientoOk()` o `api.simularBiometriaOk()` y actualiza el estado visual en la pantalla
- [x] 7.3 Cuando ambas secciones están completadas, mostrar mensaje de perfil listo y enlace a Mis exámenes
- [x] 7.4 Mostrar placeholder explícito ("Contenido disponible próximamente — C-22") en el cuerpo de cada sección pendiente
- [x] 7.5 Verificar que con ambas secciones completadas, `api.puedeRendir()` retorna `{ puede: true }` y el banner de dashboard desaparece
- [x] 7.6 Verificar que `tsc --noEmit` pasa sin errores para este archivo

## 8. Navegador de pantallas (ScreenNavigator)

- [x] 8.1 Agregar al grupo "Estudiante" en `ScreenNavigator.tsx` los items: Dashboard (`/alumno/dashboard`), Materias (`/alumno/materias`), Mis Exámenes (`/alumno/mis-examenes`), Perfil (`/alumno/perfil`)
- [x] 8.2 Verificar que todos los items nuevos son navegables desde el ScreenNavigator y que el item activo se resalta correctamente
- [x] 8.3 Verificar que `tsc --noEmit` pasa sin errores para el ScreenNavigator actualizado
