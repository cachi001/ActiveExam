## ADDED Requirements

### Requirement: Acotado por comisión de la supervisión del tutor
La capacidad `supervisar_vivo` SHALL incluir a los roles `tutor`, `revisor`, `coordinador` y `admin_sistema`, y SHALL **excluir** al rol `proctor` (eliminado). Para el rol `tutor`, el acceso a una sesión concreta SHALL estar **acotado** a las comisiones donde el tutor está asignado como docente (pertenencia `asignar_docente`, C-73 §9). El coordinador conserva supervisión **global**. El tutor NUNCA obtiene la capacidad `revisar_sesion` (veredicto).

#### Scenario: Tutor lista solo las sesiones en vivo de sus comisiones
- **WHEN** un tutor abre el panel de supervisión en vivo
- **THEN** ve únicamente las sesiones activas de las comisiones donde está asignado como docente

#### Scenario: Coordinador ve todas las sesiones en vivo
- **WHEN** un coordinador abre el panel de supervisión en vivo
- **THEN** ve todas las sesiones activas, sin acotar por comisión

#### Scenario: Proctor ya no existe como rol de supervisión
- **WHEN** se evalúa la capacidad `supervisar_vivo`
- **THEN** el conjunto de roles habilitados NO incluye `proctor` (rol eliminado del sistema)
