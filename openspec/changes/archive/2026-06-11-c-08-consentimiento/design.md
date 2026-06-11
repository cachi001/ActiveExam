# Design — C-08 `consentimiento`

> Design del flujo de consentimiento informado: pantalla dedicada (frontend React), captura por acción afirmativa, persistencia inmutable del acuse (`Consentimiento` de C-05) y vía alternativa sin biometría. Es la base legal del tratamiento biométrico (Ley 25.326); el diseño prioriza validez jurídica, inmutabilidad y libertad del consentimiento.

## Context

El proyecto Proctoring opera bajo la Ley 25.326 (Argentina), con privacidad por diseño y por defecto, y trata el embedding como dato sensible por defecto (IN-04). La biometría es obligatoria desde el MVP (DD-03, DD-18), pero su captura requiere **consentimiento libre, expreso e informado** como base legal principal (`13_legal §Base legal`). La jurisprudencia (caso SRFP) fijó límites de legalidad, necesidad y proporcionalidad.

C-08 se inserta en el **Flujo 2, paso 1**: pantalla de consentimiento → (luego) captura biométrica. Llega con C-07 listo (examen configurado, estudiante habilitado) y C-06 (estudiante autenticado). La entidad `Consentimiento` (inmutable: id, user_id, exam_id, versión_texto, timestamp, hash) ya existe en C-05.

**Constraints**:
- **Acción afirmativa obligatoria** (RN-CO-02): sin casillas premarcadas, sin consentimiento por defecto. El sistema rechaza registrar un acuse sin acción afirmativa explícita.
- **Texto versionado** (RN-CO-01): el acuse referencia la **versión exacta** del texto mostrado, para sostener la prueba meses después.
- **Acuse inmutable** (RN-CO-01): el registro `Consentimiento` no admite UPDATE/DELETE, consistente con el patrón inmutable del proyecto.
- **Vía alternativa sin biometría** (RN-CO-05): quien no consiente accede a verificación por proctor humano, **nunca se aborta** el examen (RN-GLB-02).
- **El contenido legal del texto deriva de C-01** (DPIA + Acuerdo de Nivel de Proctoring): C-08 implementa el flujo, no redacta la política.

**Stakeholders**: estudiante (titular del dato), DPO/legal (auditan el cumplimiento), proctor (atiende la vía alternativa).

## Goals / Non-Goals

**Goals:**
- Pantalla dedicada con lenguaje claro: qué/cómo/dónde/cuánto/derechos (US-003 CA-1), texto versionado.
- Captura por acción afirmativa explícita, sin casillas premarcadas (CA-2, RN-CO-02).
- Persistencia inmutable del acuse con timestamp + hash (CA-3, RN-CO-01).
- Vía alternativa sin biometría (escalación a proctor) para quien no consiente (CA-4, RN-CO-05).
- Gate que exige consentimiento (o vía alternativa) antes de C-09.

**Non-Goals:**
- NO redactar el contenido legal del texto: deriva de C-01 (DPIA / Acuerdo de Nivel de Proctoring). C-08 versiona y registra lo aprobado.
- NO implementar la verificación biométrica (C-09) ni la verificación por proctor en vivo (panel C-15): C-08 solo **escala** a la vía alternativa.
- NO implementar los derechos del titular (DSR — C-17): C-08 los **informa** en la pantalla, no los ejecuta.
- NO modificar el modelo de datos (C-05): usa `Consentimiento`.

## Decisions

### D1 — El acuse referencia la versión exacta del texto y se hashea para inmutabilidad
**Decisión**: al consentir, se persiste `Consentimiento{user_id, exam_id, versión_texto, timestamp, hash}`, donde `hash` cubre el texto exacto mostrado + la marca de acuse. El registro es inmutable (sin UPDATE/DELETE).
**Por qué**: la prueba defendible meses después requiere demostrar **qué versión exacta** consintió el estudiante y **cuándo**. El hash sella el contenido; la inmutabilidad evita repudio o alteración. Consistente con el patrón inmutable del proyecto (audit log encadenado).
**Alternativa considerada**: guardar solo un booleano "consintió" → no prueba qué consintió ni sostiene auditoría/apelación.

### D2 — Acción afirmativa validada en backend, no solo en UI
**Decisión**: el frontend presenta la acción afirmativa sin casillas premarcadas; el backend **rechaza** (422) cualquier intento de registrar un consentimiento sin la marca explícita de acción afirmativa. La validez del consentimiento no depende solo del cliente (sensor no confiable, RN-GLB-01).
**Por qué**: RN-CO-02 exige acción afirmativa; si solo se valida en UI, un cliente manipulado podría registrar un acuse falso. La validez legal debe garantizarse server-side.
**Alternativa considerada**: confiar en el checkbox del cliente → consentimiento falsificable, sin valor legal.

### D3 — No consentir NO aborta el examen: escala a la vía alternativa
**Decisión**: si el estudiante no consiente, el sistema ofrece la vía alternativa sin biometría (escalación a proctor humano en vivo) en lugar de bloquear. El examen continúa por la ruta alternativa.
**Por qué**: RN-CO-05 + RN-GLB-02 — sin alternativa, el consentimiento estaría coaccionado (consentir o no rendir), lo que lo invalida legalmente. La alternativa hace el consentimiento genuinamente libre.
**Alternativa considerada**: bloquear el examen si no consiente → vicia el consentimiento (no es libre); viola RN-GLB-02.

### D4 — El consentimiento es un gate explícito antes de C-09
**Decisión**: la habilitación de la verificación biométrica (C-09) se condiciona a un `Consentimiento` válido registrado **o** a la elección de la vía alternativa. Un estudiante sin ninguno de los dos no avanza a la captura biométrica.
**Por qué**: la captura biométrica sin base legal es un tratamiento ilícito. El gate hace que sea imposible llegar a C-09 sin haber resuelto el consentimiento.
**Alternativa considerada**: consentimiento opcional / posterior → riesgo de capturar biometría sin base legal.

## Arquitectura (frontend + backend)

```
[FRONTEND React]  Pantalla dedicada de consentimiento (lenguaje claro, texto versionado)
   - Muestra: qué / cómo / dónde / cuánto / derechos del titular
   - Acción afirmativa explícita (sin casillas premarcadas)
   - Opción visible: "No consiento → verificación alternativa por proctor"
        │
        │  POST /api/v1/consent  { exam_id, version_texto, affirmative_action: true }
        │  POST /api/v1/consent/alternative  { exam_id }   (vía sin biometría)
        ▼
[BACKEND FastAPI — application]
   RecordConsent:
     - valida acción afirmativa (D2) → si falta, 422
     - calcula hash(texto_exacto + acuse)
     - persiste Consentimiento{user_id, exam_id, versión_texto, timestamp, hash} INMUTABLE (D1)
   ChooseAlternativeVerification:
     - registra elección de vía alternativa, escala a proctor (D3)
   ConsentGate (D4):
     - C-09 consulta: ¿consentimiento válido o vía alternativa elegida? si no → no habilita biometría
        │
        ▼
[domain/infra] entidad Consentimiento (C-05, inmutable); repositorio sin UPDATE/DELETE
```

## Mapa de requisitos → reglas/criterios

| Capability | Regla / Criterio | Verificación |
|------------|------------------|--------------|
| `informed-consent-presentation` | RN-CO-01, US-003 CA-1 | pantalla con qué/cómo/dónde/cuánto/derechos; texto versionado |
| `affirmative-consent-capture` | RN-CO-02, US-003 CA-2 | registro sin acción afirmativa → rechazado (422) |
| `immutable-consent-record` | RN-CO-01, US-003 CA-3 | acuse con timestamp+hash; UPDATE/DELETE rechazados |
| `no-biometric-alternative-path` | RN-CO-05, RN-GLB-02, US-003 CA-4 | no consentir → escala a proctor, no aborta |
| `consent-gate` | RN-CO-01, DD-03 | sin consentimiento/alternativa → biometría no habilitada |

## Risks / Trade-offs

- **[Consentimiento falsificado por cliente manipulado]** → Mitigación: D2 — validación de acción afirmativa server-side; el cliente es sensor no confiable (RN-GLB-01).
- **[Acuse no defendible en apelación (no se sabe qué versión consintió)]** → Mitigación: D1 — versión_texto + hash del texto exacto, registro inmutable.
- **[Consentimiento coaccionado (sin alternativa real)]** → Mitigación: D3 — vía alternativa sin biometría obligatoria, escalación a proctor, nunca abort.
- **[Captura biométrica sin base legal]** → Mitigación: D4 — gate explícito antes de C-09.
- **[Texto desalineado con el DPIA]** → Mitigación: el contenido deriva de C-01; el versionado permite actualizar el texto y re-pedir consentimiento sin invalidar acuses previos de versiones anteriores.
- **Trade-off aceptado**: la vía alternativa carga trabajo humano sobre el proctor; es el costo de un consentimiento genuinamente libre y es coherente con que la red de seguridad del sistema es la revisión humana.

## Migration Plan

1. Implementar `RecordConsent` (con validación de acción afirmativa y hash) y `ChooseAlternativeVerification` sobre la entidad `Consentimiento` inmutable de C-05.
2. Implementar la pantalla dedicada (frontend) con texto versionado, lenguaje claro y la opción de vía alternativa.
3. Implementar `ConsentGate` consumible por C-09.
4. Tests: registro inmutable (UPDATE/DELETE rechazados), hash del texto, rechazo sin acción afirmativa (422), ruta alternativa escala a proctor sin abortar, gate bloquea biometría sin consentimiento.
5. **Criterio de salida**: `openspec validate --strict` ✓ y tests del scope verdes → desbloquea C-09.

**Rollback**: el acuse es inmutable por diseño; no hay rollback de un consentimiento registrado (es prueba legal). Revertir el change implica deshabilitar la pantalla y el gate, no borrar acuses.

## Open Questions

- ¿Menores de 18 con consentimiento parental? → depende de C-01 (gate legal). Si C-01 lo exige, el flujo de C-08 se extiende con consentimiento del responsable parental (versión de texto diferenciada). C-08 deja el versionado preparado para ello.
- ¿La vía alternativa requiere disponibilidad garantizada de proctor en la ventana del examen? → se coordina con C-02 (designación de revisores/proctores) y la calendarización de C-07.
