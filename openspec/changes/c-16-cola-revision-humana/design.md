# Design — C-16 `cola-revision-humana`

> Design técnico de producción de la **revisión humana asíncrona** (Flujo 7, UC-04). Cola por score, filtrada por jurisdicción; apertura auditada con contexto completo; decisión terminal humana inmutable. **Cierra el ciclo MVP.** Principio inviolable: el sistema NUNCA sanciona automáticamente (RN-RV-07, DD-01).

## Context

Este change materializa el **propósito** del sistema: convertir toda la maquinaria previa (biometría, eventos, evidencia firmada, score) en **una decisión humana informada y trazable**. El nivel L2.5 (DD-01) y las reglas de revisión (RN-RV) son tajantes: el sistema **prioriza y presenta evidencia; la persona decide**. No hay veredicto automático en ningún punto.

**Constraints duros** (de la KB):
- **RN-RV-02**: cola ordenada por **score descendente** (mayor primero).
- **RN-RV-01 / RN-AU-07**: el revisor ve **solo su jurisdicción** (5–15% de sesiones requieren revisión; 10–20 min c/u).
- **RN-RV-03**: cada **apertura** de sesión por un revisor se registra en el audit log con **propósito declarado**.
- **RN-RV-04**: contexto completo — línea de tiempo de eventos, **clips firmados**, observaciones del proctor, output de re-inferencia, **audit log de accesos previos**.
- **RN-CC-05**: descarga de clip vía URL firmada que **expira en 15 min**.
- **RN-RV-05**: decisión terminal = **una de tres**: descartar | escalar | derivar a disciplina.
- **RN-RV-06**: decisión + fundamento **persistidos inmutables** vinculados a la evidencia.
- **RN-RV-07 / RN-DSR-04 / DD-01**: **ninguna sanción automática**; decisión final **siempre humana**.
- **RACI** (`03`): revisión flaggeadas → Responsable = Revisor, Aprobador = Coordinador; decisión disciplinaria final → dirección académica.
- **SU-03 / C-02**: dependencia co-bloqueante — sin revisores designados y capacidad sostenida, la cola se acumula y el sistema falla.

**Decisiones heredadas (no se re-deciden)**: orden por score (C-13), evidencia firmada + URL 15 min (C-12), observaciones del proctor (C-15), RBAC contextual + MFA (C-06), `Caso disciplinario` y `Audit log` (C-05).

**Stakeholders**: revisor académico (opera la cola, decide), coordinador (aprueba, RACI), dirección académica (decisión disciplinaria final), DPO/legal (garantía de no-veredicto), perito downstream (C-18 verifica la cadena).

## Goals / Non-Goals

**Goals:**
- Presentar la cola **ordenada por score** y **filtrada por jurisdicción**.
- **Auditar cada apertura** con propósito declarado y cada acceso a evidencia.
- Ofrecer el **contexto completo** (timeline, clips firmados vía URL 15 min, observaciones, re-inferencia, audit log previo).
- Capturar la **decisión terminal** (una de tres) **inmutable** vinculada a la evidencia.
- Garantizar por diseño que el sistema **nunca sanciona automáticamente**.

**Non-Goals:**
- NO calcular el score ni decidir el encolado (eso es C-13; aquí se **consume** la cola ya ordenada).
- NO producir la evidencia ni firmarla (eso es C-12; aquí se **lee** vía URL firmada).
- NO generar las observaciones del proctor (eso es C-15; aquí se **muestran**).
- NO resolver el proceso disciplinario formal completo (eso es del `Caso disciplinario` + dirección académica, fuera del sistema); aquí se **deriva** y se abre el caso.
- NO designar/capacitar revisores (eso es C-02, organizacional, co-bloqueante).
- NO emitir veredictos/sanciones automáticas — **prohibido** (RN-RV-07).

## Decisions

### D1 — Cola ordenada por score descendente, filtrada por jurisdicción
**Decisión**: la cola se construye leyendo las **sesiones flaggeadas** (de C-13), ordenadas por **score descendente**, y se filtra por la **jurisdicción** del revisor (RN-RV-02, RN-AU-07); un revisor nunca ve sesiones fuera de su área.
**Por qué**: el revisor es el recurso escaso; ordenar por score pone primero lo más sospechoso. El aislamiento por jurisdicción es un requisito de seguridad y de competencia (cada área revisa lo suyo).
**Alternativa considerada**: cola global FIFO → no prioriza el riesgo ni respeta la jurisdicción; desperdicia el tiempo del revisor.

### D2 — Apertura de sesión auditada con propósito declarado
**Decisión**: tomar/abrir una sesión de la cola escribe una entrada en el **audit log con propósito declarado** (RN-RV-03); cada acceso a un clip se audita también.
**Por qué**: la traza de "quién abrió qué, cuándo y para qué" es parte de la defendibilidad y del control independiente (auditor, `03`). Un acceso sin propósito declarado sería opaco.
**Alternativa considerada**: log de aplicación plano → no inmutable, no encadenado, no defendible ante auditoría.

### D3 — Contexto completo de solo lectura, clips vía URL firmada de 15 min
**Decisión**: el revisor accede a **timeline de eventos, clips firmados (URL firmada 15 min), observaciones del proctor, re-inferencia firmada y audit log de accesos previos** (RN-RV-04); todo de **solo lectura** (no puede alterar la evidencia, que es WORM).
**Por qué**: para decidir con criterio necesita el cuadro completo; la URL de 15 min (RN-CC-05) limita la exposición del binario; la inmutabilidad de la evidencia (C-12) garantiza que lo que ve es lo depositado.
**Alternativa considerada**: dar acceso directo al bucket → rompe el control de acceso auditado y la expiración de URL.

### D4 — Decisión terminal: exactamente una de tres, humana, inmutable
**Decisión**: el revisor emite **una** de **descartar | escalar | derivar a disciplina** (RN-RV-05); la decisión + su fundamento se persisten **inmutables** vinculados a la evidencia (RN-RV-06). La **derivación a disciplina abre un `Caso disciplinario`** cuya resolución final es de dirección académica (RACI).
**Por qué**: tres salidas terminales cubren los casos (falso positivo, necesita más investigación, va a disciplina); la inmutabilidad de la decisión la hace defendible y no repudiable.
**Alternativa considerada**: decisión editable / múltiples decisiones simultáneas → ambigüedad y repudio; rompe la trazabilidad.

### D5 — El sistema NUNCA sanciona automáticamente (gobernanza inviolable)
**Decisión**: **ningún path** del sistema emite una sanción; la decisión terminal es **siempre** una acción humana explícita del revisor (RN-RV-07, RN-DSR-04, DD-01). La derivación a disciplina **no es** una sanción: es escalar a un proceso humano (dirección académica).
**Por qué**: es el corazón de la garantía legal del sistema y del contrato de C-01; el derecho de oposición a decisiones automatizadas se cumple **por arquitectura**.
**Alternativa considerada**: auto-derivar a disciplina sobre un umbral → viola el axioma del sistema; **descartada categóricamente**.

### D6 — Requiere C-02 (capacidad humana) para cumplir su propósito
**Decisión**: el change es **inútil sin revisores designados y capacidad sostenida** (C-02, SU-03); se documenta como co-dependencia y se instrumenta la **profundidad de la cola de revisión** (métrica de negocio, `14`) para vigilar el backlog.
**Por qué**: Flujo 7 §casos de error — backlog acumulado = el sistema falla en su propósito; el cuello de botella real es humano, no técnico (SU-03, el supuesto más subestimado).
**Alternativa considerada**: ignorar la capacidad humana → la cola se llena y nadie revisa; el sistema entrega evidencia que nadie mira.

## Arquitectura de la revisión

```
SESIONES FLAGGEADAS (de C-13, score > umbral)
        │  orden por score desc + filtro por jurisdicción [D1, RN-AU-07]
        ▼
   COLA DE REVISIÓN  ───────────────►  REVISOR (Lucía)
        │                                  │ toma/abre sesión
        │                                  ▼
        │                          AUDIT LOG (append-only, propósito declarado) [D2]
        │                                  │
        ▼                                  ▼
   CONTEXTO COMPLETO (solo lectura) [D3, RN-RV-04]:
     ├─ línea de tiempo de eventos          (TimescaleDB)
     ├─ clips firmados                       (C-12, URL firmada 15 min) [RN-CC-05]
     ├─ observaciones del proctor            (C-15)
     ├─ re-inferencia server-side firmada    (C-12)
     └─ audit log de accesos previos         (C-12/C-05)
        │
        ▼
   DECISIÓN TERMINAL (humana, una de tres) [D4, D5, RN-RV-05]:
     ├─ DESCARTAR (falso positivo)
     ├─ ESCALAR (investigación adicional)
     └─ DERIVAR A DISCIPLINA ──► abre Caso disciplinario ──► dirección académica (RACI)
        │
        ▼
   persistida INMUTABLE, vinculada a la evidencia [RN-RV-06]
        ⚠ EN NINGÚN PATH el sistema sanciona automáticamente [D5 — inviolable]

   ⏳ profundidad de la cola = métrica de negocio (vigila backlog, SU-03/C-02) [D6]
```

## Modelo de datos afectado

| Entidad | Qué usa/agrega este change | Origen |
|---------|----------------------------|--------|
| `Sesión` | lee estado `flaggeada`, ordena por `score` | C-05/C-13 |
| `Evidencia` | lee clips firmados + re-inferencia (solo lectura, WORM) | C-12 |
| `Audit log` | escribe apertura (propósito) y accesos; append-only | C-05/C-12 |
| `Caso disciplinario` | crea al **derivar a disciplina**; extiende retención (hold) | C-05 |

## Risks / Trade-offs

- **[Backlog de revisión por capacidad humana insuficiente]** (SU-03, riesgo #1 de propósito) → Mitigación: D6 — co-dependencia con C-02 + métrica de profundidad de cola; el coordinador (RACI) vigila el backlog.
- **[Un path automático emite una sanción]** → Mitigación: D5 — test exhaustivo de ausencia de veredicto automático; la única salida disciplinaria es la **acción humana explícita** del revisor.
- **[Revisor accede a jurisdicción ajena]** → Mitigación: D1 — filtro por jurisdicción validado en cada acceso; test de aislamiento.
- **[Decisión editada o repudiada después]** → Mitigación: D4 — persistencia inmutable vinculada a la evidencia; el audit log encadenado registra todo.
- **[Clip accesible sin control tras la apertura]** → Mitigación: D3 — URL firmada de 15 min (RN-CC-05); cada acceso auditado.

## Migration Plan

1. Construir la cola leyendo sesiones flaggeadas (C-13), orden por score desc + filtro por jurisdicción (D1).
2. Implementar la apertura auditada con propósito declarado (D2) y la auditoría de cada acceso a evidencia.
3. Ensamblar el contexto completo de solo lectura: timeline, clips (URL 15 min de C-12), observaciones (C-15), re-inferencia (C-12), audit log previo (D3).
4. Implementar la decisión terminal (una de tres) inmutable vinculada a la evidencia; derivar abre `Caso disciplinario` (D4).
5. Garantizar y testear que **ningún path** emite sanción automática (D5).
6. Instrumentar la **profundidad de la cola de revisión** (métrica de negocio, `14`) para el backlog (D6).

**Rollback**: feature de solo lectura sobre datos ya persistidos (eventos, evidencia, score); la decisión es la única escritura y es inmutable. Desactivar el change no corrompe datos previos.

## Open Questions

Cerradas por este change:
- ¿Cómo se ordena y aísla la cola? → score desc + jurisdicción (D1).
- ¿El sistema sanciona? → **NO, jamás**; la persona decide (D5).
- ¿Qué pasa al derivar a disciplina? → abre `Caso disciplinario`, resolución humana (D4).

Fuera de alcance (otros changes):
- Cálculo del score y encolado → **C-13**.
- Producción/firma de la evidencia → **C-12**.
- Verificación de la cadena en apelación (perito) → **C-18**.
- Designación/capacitación de revisores → **C-02** (organizacional, co-bloqueante).
- Resolución del proceso disciplinario formal → dirección académica (fuera del sistema).
