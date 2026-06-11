# Proposal — C-08 `consentimiento`

> **Naturaleza del change**: segundo paso del ciclo pre-monitoreo (FASE 1, governance **ALTO**). Implementa el **consentimiento informado** que la ley argentina exige como **base legal del tratamiento biométrico** (Ley 25.326). Es la barrera legal que se atraviesa **antes** de la verificación biométrica (C-09): sin un consentimiento válido y registrado de forma inmutable, capturar y procesar el rostro del estudiante sería un tratamiento sin base legal.

## Why

La biometría es **obligatoria desde el MVP** (DD-03, DD-18), pero la captura de datos biométricos en Argentina requiere **consentimiento libre, expreso e informado** como base legal principal (`13_legal §Base legal`). El consentimiento es lo que convierte la verificación biométrica de C-09 en un tratamiento lícito.

- **RN-CO-01**: antes de habilitar el examen, el estudiante debe atravesar un flujo de consentimiento informado con **texto versionado**; el acuse se persiste con **timestamp y hash**. Sin esto, no hay habilitación legal del examen.
- **RN-CO-02**: el consentimiento debe ser **libre, expreso e informado, con acción afirmativa (no casillas premarcadas)**. Una casilla premarcada o un consentimiento por defecto **no es válido** bajo la ley y la jurisprudencia (caso SRFP: legalidad, necesidad y proporcionalidad).
- **RN-CO-05**: debe existir una **vía alternativa sin biometría** (proctor humano en vivo) para quien no consienta, de modo que el consentimiento sea **genuinamente libre**. Sin alternativa, el consentimiento estaría viciado (coaccionado por la necesidad de rendir).
- El acuse debe ser **inmutable** (timestamp + hash): es la prueba defendible, meses después, de que el estudiante consintió la versión exacta del texto que se le mostró. Si fuera mutable, no sostendría una auditoría ni una apelación.

Este change es el **gate legal a nivel de cada estudiante**, complementario al gate organizacional de C-01 (DPIA + Acuerdo de Nivel de Proctoring). C-01 autoriza el programa; C-08 registra el consentimiento individual de cada estudiante antes de tocar su biometría.

## What Changes

Agrega la capability de **consentimiento informado por estudiante y examen**, sobre la entidad `Consentimiento` (inmutable) ya modelada en C-05 y la configuración de examen de C-07. Se ubica en el Flujo 2, paso 1: **antes** de la captura biométrica.

- **Pantalla dedicada de consentimiento** (frontend) con **lenguaje claro**: qué se recolecta, cómo, dónde, por cuánto tiempo, y los derechos del titular (acceso, rectificación, eliminación, portabilidad, oposición a decisiones automatizadas). El texto es **versionado** (`versión_texto`).
- **Acción afirmativa explícita**: el estudiante debe realizar una acción positiva e inequívoca para consentir; **sin casillas premarcadas** ni consentimiento por defecto. El sistema **rechaza** registrar un consentimiento sin acción afirmativa.
- **Persistencia inmutable del acuse**: al consentir, se crea un registro `Consentimiento` con `user_id`, `exam_id`, `versión_texto`, `timestamp` y `hash` (del texto exacto + acuse). El registro es **inmutable** (no admite UPDATE/DELETE), consistente con el patrón append-only/inmutable del proyecto.
- **Vía alternativa sin biometría**: si el estudiante **no consiente**, el sistema ofrece una ruta alternativa de verificación de identidad **escalando a un proctor humano en vivo** (RN-CO-05, RN-GLB-02 "nunca abort"), en lugar de bloquear el examen.

**Posición en el flujo**: el consentimiento se exige **después** del login (C-06) y **antes** de la verificación biométrica (C-09). Un estudiante que no atravesó el consentimiento (ni eligió la vía alternativa) no puede avanzar a la captura biométrica.

## Capabilities

> Las capabilities modelan el flujo de consentimiento como base legal verificable. Cada requisito SHALL se prueba por test (registro inmutable, hash, rechazo sin acción afirmativa, ruta alternativa).

### New Capabilities

- `informed-consent-presentation`: la pantalla dedicada con lenguaje claro (qué/cómo/dónde/cuánto/derechos) y texto **versionado** que se muestra antes de la biometría.
- `affirmative-consent-capture`: la captura del consentimiento por **acción afirmativa explícita**, con rechazo de cualquier registro sin acción afirmativa (sin casillas premarcadas).
- `immutable-consent-record`: la persistencia **inmutable** del acuse (`Consentimiento`: user_id, exam_id, versión_texto, timestamp, hash), no modificable ni borrable.
- `no-biometric-alternative-path`: la **vía alternativa sin biometría** (escalación a proctor humano) para quien no consiente, garantizando que el consentimiento sea libre.
- `consent-gate`: el gate que exige consentimiento (o elección de la vía alternativa) **antes** de habilitar la verificación biométrica.

### Modified Capabilities

<!-- Ninguna. No existen specs de dominio previas en openspec/specs/ que este change modifique. -->

(Ninguna — no existen specs de dominio previas que este change modifique.)

## Impact

- **Bloquea**: C-09 (biometría-liveness). La captura biométrica **no puede ocurrir** sin un consentimiento válido registrado o la elección de la vía alternativa. C-08 es precondición legal de C-09.
- **Dependencias entrantes**: `C-07` (exam-config — el consentimiento es **por examen**; necesita un examen configurado y el estudiante habilitado contra el cual consentir). Transitivamente: C-06 (auth — el estudiante debe estar autenticado), C-05 (`Consentimiento`), C-04.
- **Relación con C-01**: C-01 produce el **DPIA y el Acuerdo de Nivel de Proctoring** que definen el contenido legal del texto de consentimiento; C-08 **implementa** el flujo que registra el acuse de ese texto por cada estudiante. El texto versionado de C-08 deriva del marco aprobado en C-01.
- **Salida que produce** (consumida downstream):
  - Acuse de consentimiento válido (o elección de vía alternativa) → gate de entrada a **C-09**.
  - Vía alternativa elegida → escalación a proctor humano (panel de C-15 / supervisión).
- **Actores afectados**: estudiante (consiente o elige la alternativa), proctor (recibe la escalación de la vía alternativa), DPO/legal (audita los acuses inmutables como evidencia de cumplimiento).
- **Privacidad por diseño**: el consentimiento es la base legal que habilita el tratamiento biométrico con **finalidad acotada** (RN-CO-04); el acuse inmutable es la prueba auditable de cumplimiento de la Ley 25.326. La vía alternativa garantiza que el consentimiento no sea coaccionado.
