# Spec — mfa-enforcement

> Capacidad de **MFA obligatorio** para roles con acceso a evidencia/administración (TOTP mín., WebAuthn recomendado — `03`, `08`). Su Done es: un rol con acceso a evidencia sin segundo factor es rechazado.

## ADDED Requirements

### Requirement: MFA obligatorio para acceso a evidencia y administración
El sistema SHALL exigir MFA (TOTP mínimo, WebAuthn recomendado) para los roles con acceso a evidencia o administración — proctor, revisor académico, coordinador, admin de exámenes, admin del sistema, auditor — conforme a `03` §RBAC y `08` §Seguridad.

#### Scenario: Rol con acceso a evidencia sin segundo factor rechazado
- **WHEN** un usuario con rol proctor/revisor/coordinador/admin/auditor intenta acceder sin haber completado el segundo factor
- **THEN** el sistema rechaza el acceso a evidencia/administración hasta que se satisface el MFA

#### Scenario: Acceso concedido con MFA satisfecho
- **WHEN** el mismo usuario completa el segundo factor (TOTP o WebAuthn) y su token lo refleja
- **THEN** el acceso al recurso de evidencia/administración es concedido (sujeto al RBAC contextual)

### Requirement: TOTP como mínimo, WebAuthn recomendado
El enforcement de MFA SHALL aceptar TOTP como segundo factor mínimo y SHALL permitir WebAuthn como método recomendado, gestionado en Keycloak (`03`, `08`).

#### Scenario: Segundo factor TOTP aceptado
- **WHEN** un usuario configura y usa TOTP como segundo factor
- **THEN** satisface el requisito mínimo de MFA

#### Scenario: WebAuthn disponible como factor reforzado
- **WHEN** un usuario opta por WebAuthn
- **THEN** el sistema lo acepta como segundo factor recomendado, sin degradar la garantía respecto de TOTP
