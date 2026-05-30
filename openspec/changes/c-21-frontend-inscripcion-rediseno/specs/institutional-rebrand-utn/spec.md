# Spec — institutional-rebrand-utn

> Reemplazo total de la marca UBA por Universidad Tecnológica Nacional — Regional Mendoza en textos, IDs, emails y datos de demo.

## ADDED Requirements

### Requirement: La institución de la demo es UTN Regional Mendoza
El sistema NO SHALL mostrar referencias a "UBA" / "Universidad de Buenos Aires" en la UI; toda referencia institucional visible SHALL ser "Universidad Tecnológica Nacional — Regional Mendoza".

#### Scenario: Login y layouts muestran UTN
- **WHEN** el usuario ve el login, el footer o los breadcrumbs
- **THEN** la institución mostrada es UTN Regional Mendoza, no UBA

#### Scenario: Datos de demo coherentes con UTN
- **WHEN** la API mock provee usuarios, emails, IDs de examen y cátedras
- **THEN** usan dominios e identificadores de UTN (p. ej. `@frm.utn.edu.ar`, `UTN-*`, `EX-UTN-*`) y cátedras coherentes con la institución
