# Tasks — C-21 `frontend-inscripcion-rediseno`

> Refinamiento del frontend de demo (capa mock): inscripción con consentimiento, wizard pre-examen solo-verificación, rediseño minimalista, rebrand UTN, datos de demo completos y build verde. El Done de cada tarea es comportamiento navegable en la demo y/o `tsc` sin errores. No se buildea ni commitea sin pedido explícito (reglas duras de código #1, #2).

## 1. Fix del build (capability `frontend-build-integrity`)

- [ ] 1.1 Excluir las `*.test.ts` del `tsc` de build (tsconfig de build / `exclude`) sin borrarlas, y ajustar `lib`/`target` a ES2022 si hace falta; Done: `npx tsc --noEmit` no reporta errores de `vitest` ni de `.at()`
- [ ] 1.2 Corregir el bug de `data` indefinido en `features/biometria/BiometricVerification.tsx` (componente legacy no importado por la app nueva) sin cambiar el comportamiento de la app; Done: el archivo typechequea
- [ ] 1.3 Limpiar variables/imports sin usar que rompan el build; Done: `npx tsc --noEmit` verde en todo `src` (excluyendo tests)
- [ ] 1.4 Verificar que el dev server sigue corriendo y la app nueva no importa componentes legacy rotos; Done: `npm run dev` levanta sin error de runtime en el flujo principal

## 2. Rebrand institucional (capability `institutional-rebrand-utn`)

- [ ] 2.1 Reemplazar marca UBA → "Universidad Tecnológica Nacional — Regional Mendoza" en `Login.tsx`, `ui/shells.tsx` (footer/soporte) y breadcrumbs; Done: no quedan strings "UBA"/"Buenos Aires" visibles en la UI
- [ ] 2.2 Reemplazar emails `@uba.ar` → `@frm.utn.edu.ar` e IDs `UBA-*`/`EX-UBA-*` → `UTN-*`/`EX-UTN-*` en `lib/api.ts` y el generador de `ConfigureExam.tsx`; Done: grep `-i "uba"` en `frontend/src` sin coincidencias (salvo assets legacy en `screens/html/`)
- [ ] 2.3 Adaptar cátedras/carreras de demo a UTN (ingenierías) en vez de Medicina; Done: los exámenes de demo usan cátedras coherentes con UTN Regional Mendoza

## 3. Dashboard del estudiante (capability `student-exam-dashboard`)

- [ ] 3.1 Crear `screens/EstudianteDashboard.tsx` con dos secciones: "Exámenes disponibles" (inscribibles) y "Mis inscripciones" (con estado y acción siguiente); Done: la pantalla lista ambos grupos desde la API mock
- [ ] 3.2 Ruta y navegación: `login` (estudiante) → `/estudiante` (dashboard) en vez de caer en requisitos; Done: el login de estudiante aterriza en el dashboard
- [ ] 3.3 Estados vacío/carga; cada inscripción muestra su acción siguiente (Inscribirse / Continuar consentimiento / Rendir / Rendido); Done: las acciones reflejan el estado del gate

## 4. Inscripción con consentimiento (capability `exam-enrollment-with-consent`)

- [ ] 4.1 Crear `screens/InscripcionExamen.tsx`: detalle del examen (cátedra, fecha, duración, modalidad L2.5, qué se monitorea) + acción "Inscribirme"; Done: muestra el detalle y permite iniciar la inscripción
- [ ] 4.2 Integrar el consentimiento informado DENTRO del flujo de inscripción (reutilizar el texto versionado de la API mock): acción afirmativa sin casilla premarcada, botón deshabilitado hasta marcar (RN-CO-02); Done: no se puede confirmar sin acción afirmativa
- [ ] 4.3 Ofrecer la vía alternativa sin biometría (RN-CO-05) en la inscripción; Done: elegir la alternativa registra `via_alternativa: true` y deja al estudiante habilitado sin biometría
- [ ] 4.4 API mock: `inscribir`, `registrarConsentimientoInscripcion` (sella version+timestamp+hash, rechaza sin acción afirmativa), `misInscripciones`, `examenesDisponibles`, `puedeRendir`; Done: el estado de la inscripción transiciona a `habilitado` tras consentir
- [ ] 4.5 Mover `Consent.tsx` fuera del pre-examen (deja de ser paso del wizard); Done: el consentimiento ya no aparece antes de rendir

## 5. Wizard pre-examen solo-verificación (capability `pre-exam-verification-wizard`)

- [ ] 5.1 Crear el wizard unificado pre-examen (requisitos → biometría → sala de espera) reutilizando `EquipmentCheck.tsx`/`Biometria.tsx`/`SalaEspera.tsx`, SIN paso de consentimiento; Done: el wizard no presenta consentimiento
- [ ] 5.2 Indicador de pasos honesto del wizard (no "x/7" heredado); Done: el contador refleja los pasos reales del wizard
- [ ] 5.3 Gate de entrada: si el estudiante no está `habilitado` para ese examen, el wizard lo deriva al dashboard a inscribirse; Done: entrar sin habilitación redirige a inscribirse
- [ ] 5.4 Vía alternativa: si `via_alternativa`, el wizard saltea biometría y muestra "verificación por proctor humano"; Done: el flujo alternativo no exige biometría

## 6. Rediseño minimalista y datos de demo (capabilities `minimalist-ui-system`, `demo-data-completeness`)

- [ ] 6.1 Unificar jerarquía/espaciado/microcopy en las pantallas tocadas usando el UI kit existente; una acción primaria clara por pantalla; Done: pantallas consistentes con los tokens del design system
- [ ] 6.2 Agregar estados vacío/carga/error donde falten (proctor, revisor, reportes, auditoría, dashboard); Done: ninguna pantalla con dato asíncrono queda sin esos estados
- [ ] 6.3 Enriquecer la data de demo (más exámenes, sesiones, eventos, métricas, usuarios) coherente con UTN; Done: cada pantalla de staff muestra contenido realista y completo
- [ ] 6.4 Actualizar `ScreenNavigator.tsx` y la navegación para reflejar el flujo nuevo (dashboard, inscripción, wizard); Done: el navegador de demo recorre el flujo completo nuevo

## 7. Sincronización de specs de dominio

- [ ] 7.1 Actualizar specs de C-08 (`consent-gate`, `informed-consent-presentation`) para fijar que el consentimiento se captura en la inscripción y el gate se da por resuelto antes de rendir; Done: specs de C-08 reflejan el reorden sin perder garantías (acción afirmativa, inmutabilidad, hash, vía alternativa)
- [ ] 7.2 Agregar nota de posición de flujo en C-09 (la verificación biométrica es el único gate pre-examen, con consentimiento ya resuelto upstream); Done: spec/nota de C-09 actualizada
- [ ] 7.3 Registrar C-21 en `CHANGES.md` (árbol/fase Refinamiento); Done: C-21 aparece en el índice con sus dependencias

## 8. Cierre del change

- [ ] 8.1 Verificación manual del flujo completo del estudiante en `npm run dev` (login → dashboard → inscripción+consentimiento → wizard solo-verificación → examen → cierre); Done: el flujo nuevo navega sin romper
- [ ] 8.2 Confirmar `npx tsc --noEmit` verde y `vite build` produce bundle (corrido solo a pedido / para cierre, regla dura #1); Done: build sin errores
