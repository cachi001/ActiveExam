# Spec — suspicious-activity-catalog

> Catálogo canónico de actividad sospechosa (visión + navegador) que mapea cada tipo de actividad a un `tipo` de evento del dominio y a una severidad, compatible con el `event-schema-contract` de C-10 (RN-EV-04). Es la fuente de verdad para `TipoEvento`, los labels de UI y el checklist de cobertura del harness.

## ADDED Requirements

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
