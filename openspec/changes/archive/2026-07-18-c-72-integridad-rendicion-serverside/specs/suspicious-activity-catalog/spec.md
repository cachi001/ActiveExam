## ADDED Requirements

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
