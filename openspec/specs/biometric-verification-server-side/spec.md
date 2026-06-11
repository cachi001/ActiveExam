# biometric-verification-server-side Specification

## Purpose
TBD - created by archiving change c-59-verificacion-biometrica-server-side. Update Purpose after archive.
## Requirements
### Requirement: Verificación 1:1 server-side identificada por JWT

El sistema SHALL exponer un endpoint autenticado que compara el embedding facial vivo capturado por el cliente contra el embedding de referencia VIGENTE del usuario, identificado por el `sub` de su JWT (rol `estudiante`), sin que el cliente envíe ni reciba el embedding de referencia.

El endpoint SHALL recibir únicamente `embedding_vivo` y un `umbral` opcional; MUST NOT aceptar el embedding de referencia en el body (schema `extra='forbid'`). El sistema SHALL recuperar el embedding de referencia vigente desde la base de datos por el identidad del JWT, descifrarlo server-side reusando el servicio de cifrado existente (Fernet), y comparar por distancia coseno con el umbral conservador por defecto (0.35) cuando no se provea uno.

La respuesta SHALL contener `distancia`, `es_match` y `umbral`. El embedding de referencia descifrado MUST NOT incluirse en la respuesta, MUST NOT loguearse, y MUST NOT persistirse en claro (Ley 25.326; cliente = sensor no confiable).

#### Scenario: Embedding vivo cercano a la referencia vigente

- **WHEN** un estudiante autenticado con embedding de referencia vigente envía un `embedding_vivo` cuya distancia coseno a la referencia descifrada es menor que el umbral
- **THEN** el sistema responde `200` con `es_match=true` y la `distancia` calculada server-side
- **AND** el embedding de referencia no aparece en la respuesta ni en los logs

#### Scenario: Embedding vivo lejano a la referencia vigente

- **WHEN** un estudiante autenticado con embedding de referencia vigente envía un `embedding_vivo` cuya distancia coseno a la referencia es mayor o igual que el umbral
- **THEN** el sistema responde `200` con `es_match=false` y la `distancia` calculada
- **AND** el sistema no emite veredicto disciplinario (la verificación prioriza, no sanciona)

#### Scenario: El cliente intenta enviar el embedding de referencia

- **WHEN** el body incluye un campo de embedding de referencia además del `embedding_vivo`
- **THEN** el sistema responde `422` por campo no declarado (schema `extra='forbid'`)

#### Scenario: Embedding vivo de dimensión inválida

- **WHEN** un estudiante autenticado envía un `embedding_vivo` vacío o con dimensión distinta a la de la referencia (128)
- **THEN** el sistema responde `422` con un mensaje claro de embedding no comparable
- **AND** la respuesta distingue este caso del de match fallido

### Requirement: Distinción explícita de "sin referencia vigente"

El sistema SHALL responder `404` cuando un estudiante autenticado solicita la verificación 1:1 y NO posee un embedding de referencia vigente, de modo que el cliente pueda distinguir "no hay referencia cargada" de "match fallido" y de "embedding vivo inválido".

#### Scenario: Estudiante sin embedding de referencia vigente

- **WHEN** un estudiante autenticado sin embedding de referencia vigente solicita la verificación 1:1
- **THEN** el sistema responde `404` con un mensaje que indica que debe completar el enrollment de referencia
- **AND** la respuesta no es un `200` con `es_match=false`

### Requirement: Consulta de estado de referencia para el gate del cliente

El sistema SHALL exponer un endpoint autenticado (rol `estudiante`) que informa si el usuario posee un embedding de referencia vigente, devolviendo un booleano. Este endpoint MUST NOT devolver el embedding ni el identificador de la referencia; solo el estado.

#### Scenario: El estudiante tiene referencia vigente

- **WHEN** un estudiante autenticado con embedding de referencia vigente consulta el estado de su referencia
- **THEN** el sistema responde `200` con `tiene_referencia_vigente=true`
- **AND** la respuesta no contiene el embedding ni el identificador de la referencia

#### Scenario: El estudiante no tiene referencia vigente

- **WHEN** un estudiante autenticado sin embedding de referencia vigente consulta el estado de su referencia
- **THEN** el sistema responde `200` con `tiene_referencia_vigente=false`

### Requirement: Autenticación obligatoria en la verificación server-side

El sistema SHALL exigir un Bearer JWT válido de rol `estudiante` en el endpoint de verificación server-side y en el de estado de referencia. Sin token válido el sistema SHALL responder `401`; con un token de rol incorrecto SHALL responder `403`.

#### Scenario: Solicitud sin token

- **WHEN** se solicita la verificación server-side o el estado de referencia sin Bearer token
- **THEN** el sistema responde `401`

#### Scenario: Token con rol incorrecto

- **WHEN** se solicita la verificación server-side con un token cuyo rol no es `estudiante`
- **THEN** el sistema responde `403`

### Requirement: Conservación del endpoint stateless de verificación (demo)

El sistema SHALL conservar el endpoint stateless de verificación 1:1 existente (`POST /api/v1/proctoring/biometria/verificar`), que recibe ambos embeddings del cliente y no consulta la base de datos, para retrocompatibilidad y modo demo. El contrato de ese endpoint MUST NOT cambiar.

#### Scenario: El endpoint stateless sigue operativo

- **WHEN** un cliente en modo demo invoca el endpoint stateless con `embedding_vivo` y `embedding_referencia`
- **THEN** el sistema responde `200` con `distancia`, `es_match` y `umbral`, sin consultar la base de datos

