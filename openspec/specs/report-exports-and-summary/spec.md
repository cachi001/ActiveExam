# Spec — report-exports-and-summary

> Exports (CSV/JSON) y sumario institucional del período, ambos con minimización de PII (agregado por defecto; nominal solo con permiso + audit, Ley 25.326) y sin emitir veredictos agregados (RN-SC-01, DD-01).

## ADDED Requirements

### Requirement: Exports de reportes con minimización de PII
El sistema SHALL permitir **exportar** los reportes/agregados en formatos institucionales (CSV/JSON); los exports SHALL ser **agregados/estadísticos por defecto** (sin PII), y el export **nominal** SHALL requerir permiso (RBAC contextual) y SHALL quedar **auditado** (Ley 25.326, privacidad por diseño).

#### Scenario: Export agregado sin PII
- **WHEN** se exporta un reporte agregado (por examen, distribución, sumario)
- **THEN** el archivo exportado contiene datos estadísticos agregados y no expone datos personales identificables

#### Scenario: Export nominal requiere permiso y queda auditado
- **WHEN** un rol autorizado exporta un reporte con datos nominales
- **THEN** el sistema valida el RBAC contextual, registra el acceso en el audit log y solo entonces produce el export

#### Scenario: Export nominal sin permiso es rechazado
- **WHEN** un solicitante sin permiso intenta exportar datos nominales
- **THEN** el sistema rechaza el export y no produce ningún archivo con PII

### Requirement: Sumario institucional agregado sin veredicto
El sistema SHALL generar un **sumario institucional** del período para dirección académica (volumen de exámenes/sesiones, distribución global de scores, tasa de revisión, decisiones humanas agregadas); el sumario SHALL ser **agregado** y NO SHALL emitir veredictos, sanciones ni rankings nominales de estudiantes (RN-SC-01, RN-RV-07, Ley 25.326).

#### Scenario: Sumario institucional agregado del período
- **WHEN** se solicita el sumario institucional de un período
- **THEN** el sistema devuelve métricas agregadas (volumen, distribución global, tasa de revisión, decisiones humanas agregadas) sin datos personales identificables

#### Scenario: El sumario no emite veredictos ni rankings nominales
- **WHEN** se genera el sumario institucional
- **THEN** el sumario no contiene veredictos, sanciones ni un ranking nominal de estudiantes por riesgo
