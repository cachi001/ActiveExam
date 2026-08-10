# Spec — post-exam-reports

> Reportes agregados por examen y por estudiante sobre datos consolidados (score final de C-13, decisiones humanas de C-16). Agregado por defecto; el reporte nominal por estudiante requiere RBAC contextual y queda auditado (Ley 25.326, privacidad por diseño).

## ADDED Requirements

### Requirement: Reporte por examen agregado
El sistema SHALL generar, para un examen cerrado, un **reporte agregado** que combine la **distribución de scores** y el **conteo de sesiones por estado terminal** (archivada / flaggeada / revisada con su decisión humana), leyendo los datos consolidados de C-13 y C-16 sin recalcular el score ni re-decidir la revisión.

#### Scenario: Reporte por examen sobre datos consolidados
- **WHEN** se solicita el reporte de un examen cerrado
- **THEN** el reporte presenta la distribución de scores y los conteos por estado terminal calculados a partir de los agregados ya consolidados, sin recorrer la hypertable cruda ni recomputar el score

#### Scenario: El reporte por examen es agregado, sin PII por defecto
- **WHEN** se genera el reporte por examen
- **THEN** el reporte muestra datos estadísticos agregados y no expone datos personales identificables de estudiantes por defecto

### Requirement: Reporte por estudiante con acceso nominal restringido y auditado
El reporte **por estudiante** SHALL exponer la línea de tiempo agregada de sus sesiones (score final, eventos por severidad, decisiones humanas asociadas) y, por ser un **acceso a datos personales**, SHALL requerir **RBAC contextual** (jurisdicción del solicitante, C-06) y SHALL escribir el acceso en el **audit log** (Ley 25.326).

#### Scenario: Acceso nominal dentro de jurisdicción queda auditado
- **WHEN** un rol autorizado (revisor/coordinador) accede al reporte de un estudiante dentro de su jurisdicción
- **THEN** el sistema entrega el reporte y registra el acceso a datos personales en el audit log

#### Scenario: Acceso nominal fuera de jurisdicción es rechazado
- **WHEN** un solicitante intenta acceder al reporte de un estudiante fuera de su jurisdicción contextual
- **THEN** el sistema rechaza el acceso y no expone los datos personales

### Requirement: Reportes de solo-lectura sin re-decisión
Los reportes SHALL ser de **solo-lectura** sobre fuentes consolidadas: NO SHALL recalcular el score (propiedad de C-13) ni re-decidir las decisiones de revisión (propiedad de C-16).

#### Scenario: El reporte no muta scores ni decisiones
- **WHEN** se genera cualquier reporte por examen o por estudiante
- **THEN** los scores finales y las decisiones humanas de revisión permanecen inalterados (el reporte solo lee y agrega)
