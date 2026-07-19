# suspicious-activity-catalog

## Purpose

Define el catálogo canónico de actividad sospechosa (visión + navegador) que mapea cada actividad a un `tipo` de evento del dominio y a su severidad. Es la fuente de verdad consumida por las reglas de transición (que producen los eventos), por el frontend (labels y descripciones de UI), por el scoring y por el checklist de cobertura del harness, compatible con el `event-schema-contract` de C-10 (RN-EV-04).
## Requirements
### Requirement: Catálogo de actividad sospechosa de visión
El sistema SHALL declarar el mapeo de cada actividad sospechosa de visión a un tipo de evento del dominio y a una severidad: rostro ausente sostenido (`rostro_ausente`, media), múltiples rostros (`multiples_rostros`, alta), mirada desviada sostenida (`mirada_desviada_sostenida`, media). Estos tipos SHALL coincidir con los emitidos por las reglas de transición.

#### Scenario: Consulta del catálogo de visión
- **WHEN** un consumidor (UI, checklist de cobertura, scoring) consulta el catálogo por actividad de visión
- **THEN** obtiene el `tipo` de evento del dominio y la severidad asociada para rostro ausente, múltiples rostros y mirada desviada sostenida

### Requirement: Catálogo de actividad sospechosa de navegador
El sistema SHALL declarar el mapeo de cada actividad sospechosa de navegador/entorno a un tipo de evento y severidad: pérdida de foco de ventana (`perdida_de_foco`, baja), cambio o apertura de pestaña (`cambio_pestana`, media), monitor adicional (`monitor_adicional`, alta), salida de pantalla completa (`salida_pantalla_completa`, media) y copiar/pegar (`copiar_pegar`, media).

#### Scenario: Consulta del catálogo de navegador
- **WHEN** un consumidor consulta el catálogo por actividad de navegador
- **THEN** obtiene el `tipo` de evento y la severidad para pérdida de foco, cambio de pestaña, monitor adicional, salida de pantalla completa y copiar/pegar

### Requirement: Tipos de evento registrados en el dominio
Cada tipo del catálogo SHALL estar registrado como `TipoEvento` válido del dominio con su descripción y etiqueta de UI, de modo que cualquier evento producido sea reconocido por el frontend y consistente con el `event-schema-contract` de C-10.

#### Scenario: Un tipo nuevo del catálogo se emite
- **WHEN** las reglas de transición emiten un evento de tipo `cambio_pestana`, `salida_pantalla_completa` o `copiar_pegar`
- **THEN** el frontend reconoce el tipo, lo muestra con su etiqueta y descripción, y el tipo es válido según el contrato de evento

#### Scenario: Tipo desconocido
- **WHEN** se intenta registrar o mostrar un evento cuyo `tipo` no pertenece al catálogo
- **THEN** el sistema lo trata como tipo no catalogado y no lo presenta como actividad sospechosa reconocida del catálogo

### Requirement: Catálogo de actividad sospechosa de ciclo de vida de la sesión

El sistema SHALL declarar el mapeo de la reanudación de una rendición a un tipo de evento del dominio y a una severidad, discriminando por **duración de la ausencia**: reanudación rápida (`recarga_pagina`, baja) y reanudación tras ausencia prolongada (`reanudacion_tardia`, media). La discriminación por duración SHALL existir porque la reanudación en sí NO es señal de conducta indebida —un corte de energía, una caída de red o un cierre inesperado del navegador la producen— mientras que la **duración de la ausencia** sí lo es. Los umbrales de severidad SHALL derivarse de la duración medida, NOT del hecho de reanudar.

#### Scenario: Consulta del catálogo de ciclo de vida

- **WHEN** un consumidor (UI, checklist de cobertura, scoring) consulta el catálogo por actividad de reanudación
- **THEN** obtiene el `tipo` de evento del dominio y la severidad asociada para reanudación rápida y reanudación tardía

#### Scenario: Reanudación rápida se cataloga como severidad baja

- **WHEN** una rendición se reanuda tras una ausencia breve, compatible con una recarga o un cierre accidental
- **THEN** el evento se cataloga como `recarga_pagina` con severidad baja

#### Scenario: Reanudación tras ausencia prolongada se cataloga como severidad media

- **WHEN** una rendición se reanuda tras una ausencia prolongada
- **THEN** el evento se cataloga como `reanudacion_tardia` con severidad media

### Requirement: Los tipos de reanudación están registrados en el dominio

Cada tipo nuevo del catálogo SHALL estar registrado como `TipoEvento` válido del dominio con su descripción y etiqueta de UI, de modo que el frontend lo reconozca y sea consistente con el `event-schema-contract` de C-10. Los tipos SHALL tener peso configurable en `evento_score_config`, sembrado con un valor **conservador**, de modo que el peso pueda recalibrarse desde la configuración del sistema **sin modificar código**.

#### Scenario: El frontend reconoce los tipos nuevos

- **WHEN** se emite un evento de tipo `recarga_pagina` o `reanudacion_tardia`
- **THEN** el frontend lo muestra con su etiqueta y descripción, y el tipo es válido según el contrato de evento

#### Scenario: El peso de la reanudación es recalibrable sin desplegar

- **WHEN** un administrador de sistema ajusta el peso de `recarga_pagina` en la configuración de scoring
- **THEN** las consolidaciones posteriores usan el peso nuevo, sin cambios de código

#### Scenario: El peso sembrado es conservador

- **WHEN** se instalan los tipos nuevos en la configuración de scoring
- **THEN** su peso por defecto SHALL ser conservador, de modo que la reanudación por sí sola NO SHALL empujar una sesión sobre el umbral de encolado para revisión humana

