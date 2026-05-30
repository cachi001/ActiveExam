# Proposal — C-21 `frontend-inscripcion-rediseno`

> **Naturaleza del change**: refinamiento de la **capa de presentación de demo** (FASE Refinamiento, governance **MEDIO**). Opera sobre el frontend React que corre contra la **API mock en memoria** ([[frontend-demo-mock-layer]]), no sobre el backend real. No introduce lógica de dominio nueva: **reordena** el flujo de consentimiento/verificación ya modelado en C-08/C-09 y completa las pantallas que faltan para que la demo muestre el panorama completo del producto. El reorden se refleja además en las specs de dominio de C-08 y C-09 (ver "Impact").

## Why

La reconstrucción del frontend (2026-05-30) dejó una demo navegable pero con tres deudas que impiden mostrar el producto completo y que, además, divergen del proceso real esperado:

1. **No existe inscripción del estudiante a un examen.** Hoy el estudiante hace login y cae directo en el chequeo de requisitos; no hay pantalla donde vea los exámenes disponibles, se inscriba y conozca de qué se trata. El producto necesita ese paso para tener un ciclo de estudiante creíble.
2. **El consentimiento está en el lugar equivocado del flujo.** Hoy se pide **justo antes de rendir** (paso 2 de 7 del pre-examen). El proceso correcto es: **al inscribirse a un examen el estudiante acepta todo** (consentimiento informado, términos, vía alternativa); el día del examen **solo se verifica** (requisitos + biometría). Pedir el consentimiento recién al rendir es tardío y mezcla la decisión legal (libre, sin apuro) con el trámite operativo del examen.
3. **El build no compila** (`tsc && vite build` falla): `vitest` no está instalado y hay un bug de variable `data` indefinida en `features/biometria/BiometricVerification.tsx`. El dev server corre porque no typechequea, pero no se puede buildear ni validar tipos.

Súmese a esto: **referencias hardcodeadas a UBA** (la institución es **UTN Regional Mendoza**) en ~20 lugares, y **falta información en las pantallas** (datos de demo pobres) para dar un panorama completo en una presentación.

> **Encuadre legal del reorden (no es solo UX).** Mover el consentimiento a la inscripción lo hace **más** libre y expreso, no menos: el estudiante decide con tiempo, sin la presión del examen inminente. Se mantienen intactas las garantías de C-08: acción afirmativa sin casillas premarcadas (RN-CO-02), texto versionado con acuse inmutable (RN-CO-01), y vía alternativa sin biometría (RN-CO-05). Lo único que cambia es **cuándo** se atraviesa el gate: en la inscripción, no antes de rendir. El día del examen el `consent-gate` ya está resuelto y solo queda **verificar identidad** (C-09).

## What Changes

Sobre el frontend de demo (capa mock), reordena el flujo del estudiante y completa la UI:

- **Dashboard del estudiante** (nuevo): exámenes disponibles para inscribirse + "Mis inscripciones" con estado (inscripto / consentimiento pendiente / habilitado para rendir / rendido). Da el panorama que hoy no existe.
- **Inscripción a un examen** (nuevo): el estudiante elige un examen, ve el detalle (cátedra, fecha, duración, modalidad de proctoring, qué se monitorea) y **atraviesa el consentimiento informado completo en este punto** — acción afirmativa, texto versionado, vía alternativa sin biometría. Al confirmar, queda **inscripto con consentimiento registrado**.
- **Wizard pre-examen unificado** (reordenado): el día del examen, un único wizard que **solo verifica** — (1) requisitos de equipo, (2) verificación biométrica/liveness, (3) sala de espera → comenzar. **Ya no se pide consentimiento acá**; el gate se da por resuelto desde la inscripción. Si el estudiante no está inscripto/consentido, el wizard lo deriva a inscribirse.
- **Rediseño minimalista UI/UX**: limpiar densidad visual, consistencia de tokens (espaciado, tipografía, jerarquía), microcopy claro en español, estados vacíos/carga/error, y navegación coherente sobre el design system existente.
- **Rebrand institucional**: reemplazar todas las referencias a **UBA / Universidad de Buenos Aires / @uba.ar / EX-UBA-\*** por **Universidad Tecnológica Nacional — Regional Mendoza / @frm.utn.edu.ar / EX-UTN-\***.
- **Datos de demo completos**: poblar la API mock con más exámenes, sesiones, eventos, métricas y usuarios coherentes con UTN, de modo que cada pantalla (proctor, revisor, admin, reportes, auditoría) muestre contenido realista.
- **Fix del build**: que `npm run build` (`tsc && vite build`) pase — resolver `vitest`, el bug `data` de `BiometricVerification.tsx` y los errores de tipos remanentes, sin romper el dev server ni los detectores reales ya cableados.

## Capabilities

> Cada capability se valida por comportamiento observable en la demo (flujo navegable + `tsc` verde). Los SHALL describen el frontend de presentación sobre la capa mock.

### New Capabilities

- `student-exam-dashboard`: el dashboard del estudiante con exámenes disponibles e inscripciones, su estado y la acción siguiente de cada uno.
- `exam-enrollment-with-consent`: la inscripción a un examen que **captura el consentimiento informado completo en el momento de inscribirse** (acción afirmativa, texto versionado, vía alternativa), dejando al estudiante inscripto y consentido.
- `pre-exam-verification-wizard`: el wizard pre-examen unificado que **solo verifica** (requisitos + biometría + sala de espera) y **no** re-solicita consentimiento; deriva a inscribirse a quien no esté habilitado.
- `minimalist-ui-system`: el rediseño minimalista y consistente de la UI/UX (tokens, jerarquía, microcopy, estados vacío/carga/error) sobre el design system existente.
- `institutional-rebrand-utn`: el reemplazo total de la marca UBA por UTN Regional Mendoza en textos, IDs, emails y datos de demo.
- `demo-data-completeness`: los datos de demo enriquecidos y coherentes que dan panorama completo a todas las pantallas.
- `frontend-build-integrity`: que el proyecto **buildee** (`tsc && vite build`) sin errores de tipos, con la suite de tests resuelta y el bug de `BiometricVerification.tsx` corregido.

### Modified Capabilities

- `consent-gate` (de C-08): el gate de consentimiento se atraviesa **en la inscripción**, no antes de rendir; antes del examen se da por resuelto. (Spec actualizada en C-08.)
- `informed-consent-presentation` (de C-08): la pantalla de consentimiento se presenta **dentro del flujo de inscripción**. (Spec actualizada en C-08.)
- la cadena de C-09 (biometría) pasa a ser el **único** paso de habilitación previo a rendir, con el consentimiento ya resuelto upstream. (Nota de posición de flujo en C-09.)

## Impact

- **Dependencias entrantes**: C-07 (exam-config — exámenes contra los que inscribirse), C-08 (consentimiento — flujo y gate que se reordena), C-09 (biometría — verificación previa a rendir). Todas a nivel de **spec/flujo**; la implementación toca solo el frontend de demo y las specs de C-08/C-09.
- **Specs de dominio actualizadas**: este change **modifica** las specs de `c-08-consentimiento` (`consent-gate`, `informed-consent-presentation`) para fijar que el consentimiento se captura en la inscripción, y agrega una **nota de posición de flujo** en `c-09-biometria-liveness` (la verificación biométrica es el único gate pre-examen, con consentimiento ya resuelto). No cambia ninguna garantía legal (acción afirmativa, inmutabilidad, hash, vía alternativa): solo el momento del flujo.
- **Backend real**: sin cambios de código en esta etapa. La demo corre sobre la API mock ([[frontend-demo-mock-layer]]). Cuando el backend implemente el flujo, deberá exponer "inscripción + consentimiento" como un paso y "habilitación para rendir" condicionada al gate ya resuelto; queda anotado para C-08/C-09 al cerrarlos.
- **Reglas duras respetadas**: PascalCase en componentes React (regla de código #7); no se buildea ni commitea sin pedido explícito (#1, #2); el sistema sigue sin sancionar automático (dominio #5) — la UI solo prioriza/visualiza; el cliente sigue siendo sensor no confiable (dominio #6) — la demo no afirma confiar en el dato crudo.
- **Actores afectados**: estudiante (gana dashboard + inscripción + flujo más limpio), y todas las vistas de staff (proctor/revisor/admin) ganan datos de demo realistas con la marca correcta.
- **No-objetivo**: este change no integra el backend real, no toca la lógica de visión/transporte ya cableada salvo para corregir tipos, y no implementa persistencia real de inscripciones (vive en la capa mock).
