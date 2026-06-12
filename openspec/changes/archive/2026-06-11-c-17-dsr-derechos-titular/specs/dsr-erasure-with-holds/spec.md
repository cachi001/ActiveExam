# Spec — dsr-erasure-with-holds

> Derecho al olvido (Flujo 9, UC-05) con verificación de holds. RN-DSR-02, RN-DSR-03, RN-DSR-04.

## ADDED Requirements

### Requirement: Verificación de holds antes de eliminar
El sistema SHALL verificar la ausencia de casos disciplinarios abiertos (holds) vinculados al titular antes de ejecutar cualquier eliminación o anonimización.

#### Scenario: Titular sin holds
- **WHEN** un titular sin casos abiertos solicita la eliminación
- **THEN** el sistema procede con la eliminación

#### Scenario: Titular con caso abierto
- **WHEN** un titular con al menos un caso disciplinario abierto solicita la eliminación
- **THEN** el sistema difiere la eliminación, no borra nada y registra el motivo legal hasta el cierre del caso

### Requirement: Eliminación completa con residual sin datos personales
Ante una solicitud de eliminación sin holds, el sistema SHALL eliminar los embeddings cifrados del titular, revocar el acceso a los binarios (con purga física diferida a la expiración del Object Lock WORM) y anonimizar los registros de dominio, conservando un residual sin datos personales.

#### Scenario: Eliminación borra embeddings y binarios
- **WHEN** se ejecuta la eliminación sin holds
- **THEN** los embeddings del titular quedan eliminados y el acceso a sus binarios queda revocado, con la purga física registrada para la expiración del Object Lock

#### Scenario: Residual sin datos personales
- **WHEN** se anonimizan los registros de dominio del titular
- **THEN** queda un residual que prueba que la operación ocurrió, sin datos personales reidentificables

### Requirement: Oposición a decisiones automatizadas por arquitectura
El sistema SHALL garantizar el derecho de oposición a decisiones automatizadas por diseño, dado que ninguna sanción es automática (L2.5); la documentación del endpoint SHALL referenciar esta garantía.

#### Scenario: Garantía documentada
- **WHEN** se revisa el contrato del recurso DSR
- **THEN** referencia que la oposición a decisiones automatizadas está cubierta por arquitectura (revisión humana obligatoria, sin sanción automática)
