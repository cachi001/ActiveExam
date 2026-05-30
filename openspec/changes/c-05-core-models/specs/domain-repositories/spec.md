# Spec — domain-repositories

> Capacidad de **repositorios genéricos (puertos)** por dominio, con adaptadores en `infrastructure/persistence` y dominio puro (Hexagonal, `08` §Patrones). Su Done es: cada dominio tiene su puerto de repositorio y un adaptador que lo implementa.

## ADDED Requirements

### Requirement: Repositorios como puertos con dominio puro
Cada dominio (Usuario, Examen, Sesión, Asignación, Consentimiento, Embedding, Evidencia, Caso disciplinario, Evento, Audit log) SHALL exponer un repositorio genérico como **puerto** (interfaz en `domain`/`application`) con su adaptador en `infrastructure/persistence`, sin que el dominio importe SQLAlchemy.

#### Scenario: Puerto de repositorio definido por dominio
- **WHEN** se revisa la capa de dominio/aplicación
- **THEN** existe una interfaz de repositorio (puerto) por dominio, sin dependencias de SQLAlchemy ni de la infraestructura concreta

#### Scenario: Adaptador SQLAlchemy en infraestructura
- **WHEN** se revisa `infrastructure/persistence`
- **THEN** cada puerto tiene un adaptador SQLAlchemy que lo implementa, sustituible sin tocar el dominio (Hexagonal)

### Requirement: Operaciones de repositorio respetan las invariantes del dominio
Los repositorios SHALL respetar las invariantes del modelo: no exponer `update`/`delete` para el audit log ni `update` para el Consentimiento, y delegar la restricción de estado de Sesión y la inmutabilidad del audit log a las garantías de motor (enum/constraint y trigger).

#### Scenario: Repositorio del audit log es solo-append
- **WHEN** se usa el repositorio del audit log
- **THEN** solo expone operaciones de inserción y lectura (sin update/delete), coherente con el trigger append-only de la base

#### Scenario: Repositorio del Consentimiento sin update
- **WHEN** se usa el repositorio del Consentimiento
- **THEN** no expone operación de modificación, coherente con su inmutabilidad
