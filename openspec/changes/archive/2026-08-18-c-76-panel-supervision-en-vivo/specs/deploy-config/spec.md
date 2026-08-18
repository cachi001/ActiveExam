## ADDED Requirements

### Requirement: Configuración de deploy sin Keycloak (auth = JWT propio)

La configuración de infraestructura/deploy del proyecto SHALL reflejar que la autenticación real es el **JWT propio** (`auth_provider="jwt"`, emisor propio `own_issuer` de C-55) + login local, y NO SHALL levantar Keycloak como pieza operativa del stack por defecto. Las piezas de deploy atadas exclusivamente a Keycloak que no estén en uso (servicio `keycloak` en Docker Compose, su `depends_on` en el servicio `api`, variables `KEYCLOAK_*`/`KC_*` en las plantillas de entorno, artefactos bajo `infra/keycloak/`, y referencias en el reverse proxy si las hubiera) SHALL removerse.

El código del backend que soporta `auth_provider="keycloak"` como modo alternativo (settings `keycloak_*` en `app/config.py`, validador multi-issuer) NO SHALL eliminarse en este change salvo confirmación explícita: es una capacidad de dominio (abstracción de proveedor de auth de C-55), no una pieza de deploy muerta. Este alcance es **solo limpieza de configuración de deploy**.

#### Scenario: El stack por defecto no incluye Keycloak
- **WHEN** se levanta el stack de deploy con la configuración por defecto
- **THEN** no se inicia ningún servicio `keycloak` y ningún otro servicio depende de él para arrancar

#### Scenario: Las plantillas de entorno no exponen credenciales de Keycloak no usadas
- **WHEN** se revisa la plantilla de variables de entorno de deploy
- **THEN** no contiene variables `KEYCLOAK_*`/`KC_*` que no correspondan a una pieza efectivamente levantada

#### Scenario: La abstracción de proveedor de auth se preserva
- **WHEN** se ejecuta la limpieza de deploy
- **THEN** el código que permite `auth_provider="keycloak"` como modo alternativo permanece intacto (no es parte del alcance de esta limpieza)
