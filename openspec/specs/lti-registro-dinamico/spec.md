# lti-registro-dinamico Specification

## Purpose
Que dar de alta un Moodle deje de ser una tarea manual frágil que se pierde cada vez que
se recrea la base, sin perder la aprobación humana explícita que protege la raíz de
confianza.
## Requirements
### Requirement: El registro dinámico crea la fila de confianza

El sistema SHALL completar el flujo de registro dinámico de LTI 1.3: además de publicar
su configuración, SHALL recibir y persistir el registro que devuelve el Platform, tomando
de ahí el `client_id` y el `deployment_id` reales. MUST NOT requerir que una persona copie
esos identificadores a mano.

#### Scenario: Un admin registra la herramienta desde Moodle

- **WHEN** un admin de Moodle registra ActiveExam por la URL de registro dinámico
- **THEN** el sistema persiste una fila en `lti_deployment_confiable` con los datos reales del registro

### Requirement: El registro nace inactivo y lo habilita una persona

El sistema SHALL crear la fila con `activo = false`. Un launch desde un deployment no
habilitado MUST rechazarse. Solo `admin_sistema` SHALL poder habilitarlo.

#### Scenario: Registro pendiente de aprobación

- **WHEN** un Moodle desconocido completa el registro dinámico
- **THEN** la fila queda inactiva y sus launches se rechazan hasta que un admin la habilite

#### Scenario: Habilitación

- **WHEN** un `admin_sistema` habilita el deployment registrado
- **THEN** los launches subsiguientes desde ese deployment se aceptan

### Requirement: El sistema avisa si la allowlist está vacía

El sistema SHALL exponer una señal de salud que advierta cuando `lti_deployment_confiable`
no tenga ninguna fila activa. Hoy la única señal es que los alumnos no pueden entrar, y
eso se descubre tarde.

#### Scenario: Base recreada

- **WHEN** la base se recrea y la allowlist queda vacía
- **THEN** la señal de salud lo reporta antes de que un alumno intente entrar

### Requirement: El allowlist se administra desde una pantalla

El sistema SHALL ofrecer una pantalla admin-only para ver, habilitar y deshabilitar
deployments. Hoy solo existe la API, así que la operación depende de que alguien sepa
armar el request a mano.

#### Scenario: Admin revisa el estado

- **WHEN** un `admin_sistema` abre la pantalla de deployments LTI
- **THEN** ve los registrados, su estado y puede habilitarlos o deshabilitarlos

