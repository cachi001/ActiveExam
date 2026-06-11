## Why

Hoy el consentimiento informado y la captura biométrica de referencia se piden como pasos del pre-examen (login → requisitos → consentimiento → biometría → …), repitiéndose en cada rendición. Esto fricciona la experiencia, multiplica la captura de datos sensibles (embedding e imagen de referencia) sin necesidad y diluye la trazabilidad legal del acuse. El alumno debería **enrollarse una sola vez en su perfil** —consentir y registrar su referencia biométrica— y quedar habilitado para inscribirse y rendir. La referencia, además, no es eterna: el *face template aging* degrada la calidad de coincidencia a 2–4 años y la Ley 25.326 impone responsabilidad reforzada sobre el dato sensible, por lo que la referencia necesita **vigencia y renovación**.

## What Changes

- **Nueva pantalla de Perfil del alumno** como hogar del *enrollment único*: consentimiento + escaneo biométrico de referencia, dado UNA vez (no por examen, no justo antes de rendir).
- **Reordenamiento del consentimiento** (desde C-08): acción afirmativa sin casilla premarcada, texto versionado con acuse inmutable y vía alternativa sin biometría, todo presentado **dentro del flujo de perfil**.
- **Escaneo biométrico de referencia en el perfil**: captura foto/embedding reutilizando el motor de visión existente (`frontend/src/vision/`, `liveness.ts`) y **guarda la imagen de referencia** del perfil como dato sensible (cifrada, eliminada al egreso, holds difieren).
- **Vigencia y renovación de la referencia**: la captura de referencia caduca cada **24 meses (configurable)**; la verificación silenciosa continua que detecta deriva del embedding puede **gatillar renovación anticipada**.
- **Escaneo de DNI opcional / flaggeado** (fase posterior): paso opcional que no bloquea el flujo principal, con resguardo legal documentado (DNI = dato sensible).
- **Gate de enrollment**: completar el perfil (consentimiento válido + referencia biométrica vigente) habilita inscribirse/rendir, conectando con el `puedeRendir` que modela C-21. **BREAKING** respecto al flujo de C-08/C-09: el gate de consentimiento se resuelve al completar el perfil, no antes de cada examen.

> Alcance demo en frontend (React + Vite + Zustand + Tailwind, mock en `frontend/src/lib/api.ts`). No se sanciona automáticamente; la verificación real es server-side (cliente = sensor no confiable).

## Capabilities

### New Capabilities
- `student-profile-enrollment`: pantalla de perfil que aloja el enrollment único (consentimiento + referencia biométrica), define el gate de "perfil completo" que habilita inscribirse/rendir.
- `biometric-reference-renewal`: vigencia de la referencia biométrica (24 meses configurable), caducidad, renovación normal y renovación anticipada gatillada por la verificación silenciosa continua.
- `optional-dni-scan`: escaneo de DNI opcional/flaggeado para fase posterior, no bloqueante, con resguardo legal del DNI como dato sensible.

### Modified Capabilities
- `consent-gate`: el gate de consentimiento se resuelve al **completar el perfil (enrollment)**, una vez, en lugar de antes de cada examen; se mantienen todas las garantías legales.
- `informed-consent-presentation`: la pantalla de consentimiento se presenta **dentro del flujo de perfil**, no como paso de pre-examen.
- `embedding-computation`: el embedding de referencia se calcula en el **enrollment del perfil** (reutilizable) y queda sujeto a **vigencia/renovación**.
- `biometric-custody-encryption`: además del embedding, se persiste la **imagen de referencia del perfil** como dato sensible (cifrada at-rest, finalidad acotada, eliminación al egreso, holds difieren), con metadato de vigencia.

## Impact

- **Frontend (demo)**: nueva ruta/pantalla de Perfil; reubicación de los pasos de consentimiento y biometría fuera del pre-examen; estado de enrollment en Zustand; mock de perfil/enrollment/vigencia en `frontend/src/lib/api.ts`; reuso de `frontend/src/vision/` y `liveness.ts`.
- **Specs**: 3 capabilities nuevas + 4 modificadas (deltas dentro de este change; no se editan archivos de C-08/C-09).
- **Dependencias de dominio**: conecta con el `puedeRendir` de C-21 (gate de habilitación). Respeta C-01/C-02 (gates legales) y la cadena de custodia (C-12).
- **Legal**: refuerza el cumplimiento Ley 25.326 (embedding + imagen de referencia + DNI = datos sensibles; eliminación al egreso; holds difieren) y agrega política de retención por vigencia de la referencia.
