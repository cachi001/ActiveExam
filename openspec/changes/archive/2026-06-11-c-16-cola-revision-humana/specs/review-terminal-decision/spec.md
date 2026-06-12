# Spec — review-terminal-decision

> Decisión terminal humana (descartar | escalar | derivar a disciplina), persistida inmutable vinculada a la evidencia, garantizando que el sistema NUNCA sanciona automáticamente (RN-RV-05, RN-RV-06, RN-RV-07, DD-01).

## ADDED Requirements

### Requirement: Decisión terminal de exactamente una de tres opciones
El revisor SHALL emitir **exactamente una** de tres resoluciones terminales: **descartar** (falso positivo), **escalar** (investigación adicional) o **derivar a proceso disciplinario** formal (RN-RV-05).

#### Scenario: Una de tres resoluciones
- **WHEN** el revisor resuelve una sesión
- **THEN** registra exactamente una de: descartar, escalar o derivar a disciplina

#### Scenario: Derivar a disciplina abre un caso
- **WHEN** el revisor deriva una sesión a proceso disciplinario
- **THEN** se abre un `Caso disciplinario` vinculado a la evidencia, cuya resolución final corresponde a dirección académica (RACI)

### Requirement: Decisión persistida inmutable vinculada a la evidencia
La decisión y su **fundamento** SHALL persistirse **inmutables**, vinculados a la evidencia mediante referencias inmutables (RN-RV-06).

#### Scenario: Decisión inmutable y trazable
- **WHEN** el revisor registra su decisión y fundamento
- **THEN** se persisten de forma inmutable, vinculados a la evidencia, sin posibilidad de edición posterior

### Requirement: El sistema NUNCA sanciona automáticamente
El sistema SHALL NOT emitir ninguna sanción ni decisión disciplinaria automática; la decisión terminal SHALL ser **siempre** una acción humana explícita del revisor (RN-RV-07, RN-DSR-04, DD-01). Derivar a disciplina es escalar a un proceso humano, no una sanción automática.

#### Scenario: Ningún path automático sanciona
- **WHEN** se recorre cualquier camino del sistema relacionado con la revisión
- **THEN** ningún path emite una sanción; la única forma de una resolución terminal es la acción humana explícita del revisor

#### Scenario: El score no decide por sí solo
- **WHEN** una sesión tiene score muy alto
- **THEN** el sistema la prioriza en la cola pero NO la sanciona ni la deriva automáticamente; un revisor humano debe abrirla y decidir
