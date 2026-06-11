## Why

El consentimiento de **perfil** (C-22) registra una sola vez el acuse PESADO del tratamiento del dato biométrico/sensible (Ley 25.326, responsabilidad reforzada): texto versionado, acción afirmativa, acuse inmutable, vía alternativa y renovación. Es la **base legal** del tratamiento. Pero la Ley 25.326 exige que cada instancia de tratamiento tenga una **finalidad/propósito específico**, y el acuse de perfil —genérico para todas las rendiciones— no la provee por examen concreto.

El `design.md` de C-22 dejó esto como **PREGUNTA ABIERTA**: *"¿Hace falta un acuse de consentimiento por-examen además del de perfil?"*. El usuario decidió el modelo de **consentimiento EN CAPAS**: el de perfil queda como base de licitud, y se agrega un **acuse LIVIANO y ESPECÍFICO por examen** que da finalidad concreta ("sabés que esa persona va a rendir ESE examen") sin re-pedir biometría ni el consentimiento pesado. **Este change C-26 resuelve esa pregunta abierta.**

## What Changes

- **Paso de acuse por-examen** en el flujo de inscripción a un examen (de C-21): antes de quedar inscripto, el alumno ve el examen específico (cátedra, fecha/hora, duración) y **qué se va a monitorear** (cámara, pantalla/foco, pestañas, etc.), y hace una **acción afirmativa** para confirmar ESA instancia de tratamiento. La pantalla **referencia** el consentimiento de perfil ya dado (C-22), no lo repite ni re-captura biometría.
- **Acuse inmutable por (estudiante, examen)**: se registra versión del texto + timestamp + hash (simulado en demo). Idempotente por par `(estudiante, examen)`.
- **Gate de habilitación actualizado (capa en capas)**: para rendir un examen se requiere `perfil_completo` (consentimiento de perfil + biometría vigente, de C-22) **Y** `acuse_examen` para ESE examen. Si falta el acuse, la inscripción/rendir deriva a completarlo (no sanciona, no bloquea silenciosamente).
- **API mock**: `registrarAcuseExamen(examenId, { afirmativo })` y `puedeRendir(examenId)` que también chequea el acuse de ESE examen, con `codigo` semántico nuevo (`acuse_examen_faltante`).

> Alcance demo en frontend (React + Vite + Zustand + Tailwind, mock en `frontend/src/lib/api.ts`). No se sanciona automáticamente (L2.5); el cliente es sensor no confiable y el acuse real se firma/sella server-side (la demo lo mockea pero las specs lo exigen como comportamiento).

## Capabilities

### New Capabilities
- `per-exam-consent-acknowledgment`: el acuse LIVIANO y ESPECÍFICO por (estudiante, examen) que da finalidad concreta a la instancia de tratamiento, referenciando el consentimiento de perfil sin repetirlo ni re-capturar biometría; acuse inmutable (versión + timestamp + hash simulado) e idempotente.

### Modified Capabilities
- `exam-enrollment` (de C-21): la inscripción a un examen incorpora el paso de acuse por-examen antes de quedar inscripto; "Mis exámenes" y el gate de rendir reflejan el estado del acuse.
- `consent-gate` (de C-22): el gate de habilitación pasa a ser **en capas** = consentimiento de perfil vigente (C-22) **Y** acuse por-examen para ESE examen; falta de acuse deriva a completarlo, no sanciona.

## Impact

- **Resuelve la PREGUNTA ABIERTA del `design.md` de C-22** (acuse por-examen además del de perfil) con el modelo en capas decidido por el usuario: el de perfil = base de licitud (acuse pesado), el por-examen = finalidad específica (acuse liviano).
- **Frontend (demo)**: paso de acuse en el flujo de inscripción (`screens/AlumnoMaterias.tsx` / `screens/AlumnoMisExamenes.tsx`); estado de acuses por examen en Zustand; mock `registrarAcuseExamen` + extensión de `puedeRendir(examenId)` en `frontend/src/lib/api.ts`.
- **Specs**: 1 capability nueva + 2 modificadas (deltas DENTRO de este change; NO se editan archivos de C-21 ni C-22).
- **Legal**: refuerza Ley 25.326 (finalidad específica por instancia de tratamiento) sin duplicar el tratamiento del dato sensible; el acuse por-examen NO re-captura ni re-procesa biometría, solo referencia el acuse de perfil vigente.
- **Dominio**: respeta L2.5 (no sanción automática; el gate flaggea/deriva) y cliente = sensor no confiable (el acuse se sella server-side; demo mockeada).
