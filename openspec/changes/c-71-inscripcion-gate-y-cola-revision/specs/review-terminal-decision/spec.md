## MODIFIED Requirements

### Requirement: Decisión terminal de exactamente una de tres opciones
El sistema SHALL modelar la decisión de revisión en **dos fases**. En la **fase de revisión** (capacidad `revisar_sesion`) el revisor SHALL emitir exactamente una de: **`sin_hallazgos`** (falso positivo; valida la nota), **`aprobado`** (revisado, legítimo; valida la nota) o **`caso_abierto`** (derivación: hay algo que resolver, el caso queda abierto). En la **fase de resolución** (capacidad `resolver_caso`), y SOLO si el caso está `caso_abierto`, la autoridad SHALL emitir exactamente una de: **`anulado_por_fraude`** (anula la nota) o **`caso_descartado`** (cierra el caso validando la nota). `caso_abierto` (antes `flaggeado_para_sumario` / `derivada`) SHALL NOT ser un veredicto por sí mismo: NO valida ni anula la nota; solo habilita la fase de resolución.

#### Scenario: La revisión emite una de tres resoluciones
- **WHEN** el revisor resuelve la fase de revisión de una sesión
- **THEN** registra exactamente una de: `sin_hallazgos`, `aprobado` o `caso_abierto`

#### Scenario: Derivar (caso_abierto) no anula la nota por sí mismo
- **WHEN** el revisor deja una sesión en `caso_abierto`
- **THEN** se abre un caso vinculado a la evidencia y la nota NO cambia hasta que la autoridad con `resolver_caso` emita `anulado_por_fraude` o `caso_descartado`

### Requirement: Decisión persistida inmutable vinculada a la evidencia
La decisión y su **fundamento** (motivo **obligatorio no vacío** en toda decisión) SHALL persistirse **inmutables** y vinculados a la evidencia mediante referencias inmutables (RN-RV-06). Los actos SHALL ser **append-only**: ningún acto previo se muta ni se borra. El efecto sobre la nota SHALL derivarse del **último acto**, de modo que una reversión se realice por un **nuevo acto compensatorio** sin alterar el registro anulatorio original.

#### Scenario: Decisión inmutable y trazable con motivo obligatorio
- **WHEN** el revisor o la autoridad registra una decisión y su motivo
- **THEN** se persisten de forma inmutable, con motivo no vacío, vinculados a la evidencia, sin posibilidad de edición posterior del acto

#### Scenario: Revertir el efecto no edita el acto previo
- **WHEN** se restituye una nota previamente anulada
- **THEN** se agrega un acto compensatorio inmutable y el acto de anulación original permanece intacto

### Requirement: El sistema NUNCA sanciona automáticamente
El sistema SHALL NOT emitir ninguna sanción ni anulación de nota automática; tanto la resolución de revisión como el veredicto de resolución (`anulado_por_fraude`) SHALL ser **siempre** actos humanos explícitos (RN-RV-07, RN-DSR-04, DD-01). El score SHALL únicamente priorizar la cola. NO SHALL existir ningún path automático desde un score/umbral hacia `anulado_por_fraude`.

#### Scenario: Ningún path automático sanciona ni anula la nota
- **WHEN** se recorre cualquier camino del sistema relacionado con la revisión
- **THEN** ningún path emite una sanción ni anula la nota; la única forma de un veredicto es un acto humano explícito con la capacidad correspondiente

#### Scenario: El score no decide por sí solo
- **WHEN** una sesión tiene score muy alto
- **THEN** el sistema la prioriza en la cola pero NO la anula ni la resuelve automáticamente; un humano debe abrirla y decidir
