# Proposal — C-18 `verificacion-cadena-apelacion`

> **Naturaleza del change**: backend **core** de cumplimiento legal. Governance **CRÍTICO** (evidencia defendible, cadena de custodia). Implementa `POST /api/v1/evidence/{id}/verify-chain` (UC-06, Flujo 8). Depende de C-12 (cadena de custodia / firmas / WORM ya construida).

## Why

El valor probatorio del sistema no está en detectar, sino en **sostener la evidencia ante una apelación** (US-009). Un caso disciplinario que llega a la justicia ordinaria (L-002) se gana o se pierde según si la evidencia es **defendible matemáticamente** y **verificable por un perito externo de forma independiente** (DD-07: "evidencia defendible matemáticamente; un perito externo valida la cadena"). Sin un mecanismo formal de verificación de la cadena de firmas, la institución solo puede argumentar "confíen en nosotros", lo cual no resiste un peritaje.

La cadena de custodia se construye en cuatro etapas criptográficas acumulativas (cliente HMAC → backend re-hash → worker firma maestra → re-inferencia firmada; RN-CC-02). Este change **cierra el ciclo**: produce, a demanda, un **certificado de verificación** de esa cadena (Flujo 8). Si la cadena está rota o un hash no valida, la evidencia **no se sostiene** y ese hecho queda **registrado** (Flujo 8 caso de error; RN-CC-03). El sistema no oculta una cadena rota: la declara.

## What Changes

Implementa el endpoint de verificación de la cadena de custodia en apelación:

- **`POST /api/v1/evidence/{id}/verify-chain`** (UC-06, Flujo 8): para una evidencia dada, **re-verifica las cuatro etapas** de la cadena de firmas y genera un **certificado de verificación** que describe el resultado etapa por etapa (cliente → backend → worker/clave maestra → re-inferencia).
- **Certificado de verificación independiente**: el certificado contiene los hashes, las firmas y las claves públicas necesarias para que un **perito externo valide la cadena por sí mismo**, sin depender del sistema que lo emitió (verificación independiente con la clave pública maestra RSA-2048 / Ed25519).
- **Detección y registro de cadena rota**: si cualquier hash recalculado no coincide o una firma no valida (RN-CC-03), el certificado declara la cadena **rota**, la evidencia **no se sostiene**, y se registra el hecho en el audit log append-only.
- **Trazabilidad de la verificación**: cada invocación de `verify-chain` queda registrada en el audit log (actor, propósito=apelación, timestamp, evidencia_id), encadenada por hash.

**BREAKING**: ninguno. Es un endpoint nuevo de solo lectura/verificación sobre evidencia existente; no muta la evidencia (que es WORM).

## Capabilities

### New Capabilities

- `evidence-chain-verification`: el endpoint `POST /api/v1/evidence/{id}/verify-chain` que re-verifica las cuatro etapas de la cadena de firmas y emite un certificado de verificación con el resultado por etapa.
- `independent-expert-verification`: la entrega, dentro del certificado, de los hashes, firmas y claves públicas que permiten a un perito externo validar la cadena de forma independiente del sistema emisor.
- `broken-chain-detection`: la detección de cadena rota (hash/firma no válidos), la declaración de que la evidencia no se sostiene y el registro del hecho en el audit log.

### Modified Capabilities

(Ninguna — consume la cadena de custodia construida en C-12; no modifica sus requisitos.)

## Impact

- **Dependencias entrantes**: C-12 (cadena de custodia: hashes, firma maestra, re-inferencia, bucket WORM, audit log encadenado). Sin esas etapas firmadas no hay cadena que verificar.
- **Decisiones que consume**: DD-07 (Object Lock + evidencia defendible matemáticamente, perito externo valida), RN-CC-02/03/07, modelo de Evidencia (`hash_cliente`, `firma_cliente`, `hash_backend`, `firma_maestra`, `output_reinferencia`) y Audit log append-only.
- **Actores afectados**: institución y **perito externo** (validan en apelación), revisor/coordinador disciplinario (presentan la evidencia), auditor (revisa la trazabilidad).
- **Riesgos mitigados**: L-002 (caso en justicia ordinaria sin evidencia defendible), R-002 (en disputa se argumenta evidencia razonable y no prueba absoluta — mitigado con cadena formal verificable). El sistema NUNCA sanciona automáticamente (L2.5): la verificación informa al proceso humano, no decide.
