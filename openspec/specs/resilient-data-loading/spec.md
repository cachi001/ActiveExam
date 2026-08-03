# resilient-data-loading Specification

## Purpose
TBD - created by archiving change c-73-persistencia-carga-cliente. Update Purpose after archive.
## Requirements
### Requirement: Un fetch fallido nunca se muestra como dato

Las pantallas que cargan datos MUST distinguir los estados `cargando`, `error`,
`vacío-real` y `cargado`. Un fetch que falla NUNCA debe renderizarse como un dato
legítimo (ni "0", ni una lista vacía silenciosa): debe mostrarse como error, con la
opción de reintentar.

#### Scenario: El fetch de exámenes falla tras recargar
- **WHEN** una pantalla intenta cargar una lista y el request falla (red, 401 por token no listo, 500)
- **THEN** la pantalla muestra un estado de error visible (no un cero ni una lista vacía)
- **AND** ofrece reintentar la carga

#### Scenario: Un cero real solo se muestra cuando la carga terminó bien
- **WHEN** la carga completó con éxito y el resultado es efectivamente vacío
- **THEN** recién ahí se muestra "0" / estado vacío como dato legítimo

#### Scenario: Mientras carga se muestra un placeholder, no un valor
- **WHEN** una métrica o lista está cargando
- **THEN** se muestra un indicador de carga (no el valor inicial vacío como si fuera dato)

### Requirement: Navegar entre páginas no vuelve a pedir todo en frío

La lectura de datos ya obtenidos MUST servirse desde un cache de cliente cuando
se vuelve a una pantalla, revalidando en segundo plano (stale-while-revalidate),
en vez de mostrar un estado de carga en frío en cada navegación.

#### Scenario: Volver a una pantalla ya visitada muestra datos al instante
- **WHEN** el usuario navega a una pantalla cuyos datos ya se cargaron recientemente
- **THEN** se muestran los últimos datos buenos de inmediato
- **AND** se revalidan en segundo plano sin bloquear la vista

#### Scenario: El dato de rendición en vivo no se sirve del cache viejo
- **WHEN** la pantalla muestra estado que debe ser siempre fresco (rendición/supervisión en vivo)
- **THEN** ese estado NO se sirve del cache stale; se pide fresco

