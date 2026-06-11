# Spec — harness-legibility-layer (delta C-53)

> El conteo de rostros (`face_count`) se presenta en lenguaje humano consistente en todas las superficies de UI, sin números crudos ni prefijos técnicos (`srv:`).

## ADDED Requirements

### Requirement: Conteo de rostros en lenguaje humano consistente
Toda superficie de UI que muestre el conteo de rostros SHALL presentarlo en lenguaje humano con pluralización correcta (ej. "sin rostros", "1 rostro detectado", "N rostros detectados") mediante un helper de presentación compartido (fuente única de la lógica de fraseo). NO SHALL mostrarse el número crudo aislado ni prefijos técnicos como `srv:`. Cuando se contrasta el conteo de cliente y servidor, cada uno SHALL rotularse explícitamente (ej. "Cliente: 2 rostros", "Servidor: 2 rostros"), conservando el indicador de discrepancia cuando difieren.

#### Scenario: badge de log humanizado
- **WHEN** el log de eventos muestra el conteo de rostros reportado por el servidor
- **THEN** lo presenta como "Servidor: N rostro(s)" (o equivalente humano), no como `srv:N`

#### Scenario: card de evento contrasta cliente y servidor con etiqueta
- **WHEN** la card de un evento muestra el conteo de rostros de cliente y servidor
- **THEN** muestra cada origen rotulado en lenguaje humano ("Cliente: N rostros", "Servidor: N rostros") y conserva el badge de discrepancia cuando los valores difieren

#### Scenario: pluralización correcta en los bordes
- **WHEN** el conteo de rostros es 0, 1 o mayor que 1
- **THEN** el texto usa la forma correcta ("sin rostros", "1 rostro detectado", "N rostros detectados") provista por el helper compartido

#### Scenario: helper compartido como fuente única
- **WHEN** se muestra el conteo de rostros en panel de señales, card de evento y log
- **THEN** las tres superficies usan el mismo helper de fraseo, sin duplicar la lógica de pluralización
