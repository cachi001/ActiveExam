# Design — C-02 `designacion-revisores`

> **Naturaleza**: documento de diseño de un **gate organizacional**, no de software. El "diseño" aquí es el **modelo de dimensionamiento humano**, la estructura del equipo de revisión, el plan de capacitación y el mecanismo de monitoreo de backlog. No hay arquitectura de código, esquema ni endpoints.

## Contexto y restricciones

- **Nivel L2.5, sin sanción automática** (DD-01): el sistema **prioriza** con un score de riesgo, pero la **decisión disciplinaria final es siempre humana** (RACI: Revisor responsable → Coordinador aprobador → Dirección académica terminal). Toda la inversión técnica del proyecto presupone que ese humano existe y tiene capacidad.
- **SU-03 — Capacidad de revisión humana sostenida**: la institución sostiene la revisión del **5–15% de las sesiones**. *Riesgo si es falso*: la evidencia se acumula sin revisión y el sistema falla en su propósito. *Validación prescrita*: designar y capacitar revisores **antes de Fase 1** y **monitorear el backlog**. Es **el supuesto más subestimado**.
- **O-003** — Capacidad insuficiente de revisión humana (Prob. Media, Impacto **Alto**, estado *acción del cliente*). Mitigación: estimación temprana de carga + capacitación + monitoreo de backlog. Este change **es** esa mitigación.
- **SU-06 — Capacity model**: objetivo operacional **1.000 concurrentes sostenido**, **~2.100 pico** multi-examen. El dimensionamiento humano se calcula sobre estos números, no sobre los 700 del discovery original.
- **Co-bloqueo del camino crítico**: la cadena cierra en C-16, pero C-16 **no cumple su propósito** sin C-02. Por eso C-02 corre en paralelo a C-01 desde el día cero, no "cuando haya tiempo".

## Decisión central: modelo de dimensionamiento humano

El número de revisores **no se adivina**: se deriva de un modelo explícito y revisable. Variables y método:

### Variables de entrada
| Variable | Símbolo | Valor de partida | Fuente |
|----------|---------|------------------|--------|
| Volumen de sesiones por ventana de examen | `V` | 1.000 sostenido / ~2.100 pico | SU-06 |
| Tasa de sesiones flaggeadas (a cola de revisión) | `f` | **5–15%** (rango; usar **15% para dimensionar conservador**) | SU-03 |
| Tiempo medio de revisión por sesión flaggeada | `t_rev` | a estimar en el piloto (estimación inicial documentada, p. ej. 10–20 min) | Flujo 7 |
| Horas productivas de revisión por revisor por día | `h` | a definir con dirección académica/RRHH | Gestión del cambio |
| Plazo objetivo de resolución del backlog | `SLA_rev` | a definir (p. ej. 48–72 h hábiles) | Coordinación operativa |

### Fórmula de dimensionamiento (capacidad sostenida)
```
sesiones_a_revisar  = V * f
carga_horas         = (V * f) * t_rev
revisores_necesarios = ceil( carga_horas / (h * SLA_rev_en_dias) ) + margen_pico
```
- **Dimensionar al PICO, no al sostenido**: se usa `f` en su extremo alto (15%) y `V` de pico (~2.100) para el cálculo de **doble cobertura en picos**, espejo de la regla de C-03 ("clavar al pico"). El sostenido (1.000 / 5%) define la **plantilla base**; el pico define el **refuerzo / on-call**.
- **Por jurisdicción**: el cálculo se reparte por área, porque el RBAC es contextual (cada revisor cubre su jurisdicción). Una jurisdicción sin revisor designado es un agujero de cobertura aunque el total agregado "cierre".
- **Margen y suplencia**: ausencias, vacaciones y rotación obligan a un `margen_pico` y a **suplentes**; un equipo dimensionado "justo" colapsa en el primer pico real.

### Por qué este modelo y no "asignar X personas"
Porque las entradas (`f`, `t_rev`) **son supuestos hasta el piloto**. El modelo se entrega con valores de partida documentados y se **re-valida con datos reales al cierre del piloto y trimestralmente el primer año** (KB 15 §recomendación 3). Lo que se congela en C-02 no es el número final, sino el **método, la plantilla inicial y el compromiso de re-dimensionar** cuando el monitoreo lo indique.

## Estructura del equipo y RACI

| Rol | Responsabilidad en el flujo de revisión | RACI |
|-----|------------------------------------------|------|
| **Revisor académico** (Lucía) | Toma sesiones de su jurisdicción; ve contexto completo; emite decisión terminal (descartar/escalar/derivar) | **R** de revisión |
| **Coordinador operativo** (Diego) | Gestiona la cola/backlog, asigna, escala a TI, lee métricas operacionales | **A** de revisión; **R** de backlog |
| **Dirección académica** | Decisión disciplinaria final; firma la confirmación de capacidad sostenida | **A/R** de decisión disciplinaria; **A** del gate |
| **Proctor en vivo** (Martín) | Supervisión en curso; alimenta observaciones que el revisor consume | C |
| **On-call / TI** (Pablo) | Disponibilidad del sistema durante ventanas de revisión; comparte capacitación (O-001) | C |

Restricciones heredadas del RBAC (KB 03): **MFA obligatorio** para todos los roles con acceso a evidencia; acceso **auditado con propósito declarado**; jurisdicción contextual. La capacitación debe cubrir estas restricciones explícitamente.

## Plan de capacitación por rol

Cinco currículas, una por rol, con evaluación verificable (no "asistió a una charla", sino "aprobó un caso práctico"):

1. **Revisor académico**: criterio sobre evidencia, las tres decisiones terminales, lectura de la línea de tiempo + clips firmados + re-inferencia, gestión de falsos positivos, propósito declarado y MFA, límites del sistema (sin sanción automática).
2. **Coordinador operativo**: gestión de cola/backlog, umbrales de alerta, escalado a TI, lectura del capacity model, doble cobertura en picos.
3. **Proctor en vivo**: panel priorizado por riesgo, mensajería al estudiante, observaciones, cierre forzado, derivación a revisión.
4. **On-call / TI**: runbooks, simulacros, doble cobertura en picos (vínculo con O-001).
5. **Transversal**: privacidad/Ley 25.326, audit log, MFA, comunicación a estudiantes (transparencia).

## Mecanismo de monitoreo de backlog

El backlog acumulado es **la señal de que SU-03 está fallando** (Flujo 7 §caso de error). Diseño del control:
- **Métrica**: tamaño de la cola de revisión y antigüedad de la sesión más vieja sin resolver, por jurisdicción.
- **Umbrales**: verde / ámbar / rojo definidos contra el `SLA_rev`. Rojo dispara **escalado a dirección académica** y activación de refuerzo/suplentes.
- **Responsable**: coordinador operativo (R), dirección académica (A en rojo).
- **Cadencia de re-validación del modelo**: al cierre del piloto y **trimestral** el primer año; cada re-validación ajusta `f` y `t_rev` con datos reales y re-dimensiona la plantilla.
- **Nota de implementación futura**: la *instrumentación* técnica de esta métrica se materializa en C-16/C-13 (la cola y el scoring), pero el **mecanismo de gobierno, los umbrales y el responsable** se definen acá, en C-02, porque son organizacionales y deben existir antes que el código.

## Riesgo: qué pasa si SU-03 falla (O-003 materializado)

Escenario explícito a documentar y mitigar:
1. **Síntoma**: el backlog supera el umbral rojo sostenidamente; la antigüedad de sesiones sin revisar crece.
2. **Consecuencia**: sesiones flaggeadas sin resolver → garantía probatoria teórica → **el sistema no cumple su propósito** aunque C-16 funcione. Riesgo reputacional y legal (R-002).
3. **Mitigaciones escalonadas**:
   - Activar **suplentes y doble cobertura** (refuerzo dimensionado al pico).
   - **Re-priorizar**: revisar primero por score descendente (ya lo hace C-16) y, si es insostenible, **subir el umbral institucional de flagging** temporalmente para reducir `f` — decisión de dirección académica, registrada.
   - **Re-dimensionar** la plantilla con los datos reales del monitoreo.
   - En el extremo, **gestión de expectativas con el patrocinador** (vínculo con el Acuerdo de Nivel de Proctoring de C-01): el alcance de revisión sostenible es una restricción real, no un ajuste de software.
4. **Prevención (lo que hace este change)**: estimar temprano, dimensionar al pico, capacitar antes de Fase 1, instalar el monitoreo desde el día uno y obtener la **firma de capacidad sostenida** que vuelve el compromiso explícito y auditable.

## Alternativas consideradas

- **Diferir la designación a Fase 1** (cuando "ya haya cola"): **rechazada**. Es exactamente el modo de fracaso de SU-03/O-003: descubrir tarde que no hay quién revise. La capacitación tiene lead time; debe correr en paralelo a C-01.
- **Dimensionar solo al sostenido (1.000 / 5%)**: **rechazada** para el refuerzo. Espeja el error que C-03 corrige en lo técnico: planificar al promedio y reventar en el pico. La plantilla base usa el sostenido; el refuerzo/on-call se dimensiona al pico (~2.100 / 15%).
- **Tercerizar la revisión a un proveedor externo**: fuera de alcance del MVP y en tensión con el RBAC por jurisdicción y con la decisión disciplinaria interna (dirección académica). Se documenta como opción de escala futura, no como entregable de C-02.

## Out of scope

- Implementación de la cola de revisión y su instrumentación técnica (eso es **C-16** / C-13 / C-15).
- Definición del umbral de score de flagging como parámetro de software (eso es C-07/C-13); acá solo se define la **palanca organizacional** de ajustarlo si el backlog colapsa.
- Cualquier código, esquema, endpoint o infraestructura.
