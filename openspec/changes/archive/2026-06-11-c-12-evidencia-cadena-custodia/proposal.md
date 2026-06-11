# Proposal — C-12 `evidencia-cadena-custodia`

> **Naturaleza del change**: feature de producción, governance **CRÍTICO**. Implementa la **cadena de custodia criptográfica de 4 etapas acumulativas** (US-008/US-009, FR-08/FR-09, Flujo 4). Es la base probatoria de todo el sistema: si la evidencia no es defendible matemáticamente ante un perito externo, el propósito disciplinario se cae. **Depende de C-10** (canal de eventos + ganador de transporte) y **usa el ganador de cola de C-03** para la etapa asíncrona del worker.

## Why

El sistema opera bajo un axioma duro: **el cliente es un sensor no confiable** (RN-GLB-01, DD-02). Toda evidencia que sube el navegador del estudiante es entrada potencialmente hostil. Sin una cadena de custodia criptográfica que un perito externo pueda validar **independientemente**, la evidencia no se sostiene en un proceso disciplinario apelado (Flujo 8, UC-06) y el sistema falla en su propósito.

El discovery exige (RN-CC-02, DD-07) que la evidencia tenga **cuatro etapas criptográficas acumulativas** — las firmas no se reemplazan, **se encadenan** — más almacenamiento WORM inmutable (Object Lock modo Compliance) y un audit log append-only con hashes encadenados. Cualquier eslabón débil rompe la defendibilidad: si el backend confiara en el hash del cliente, un adversario que manipule el clip pasaría inadvertido; si el bucket permitiera borrado, la evidencia sería repudiable; si el audit log fuera mutable, no habría traza confiable de quién accedió a qué.

Hay un SLO duro asociado: la **re-inferencia server-side + firma maestra debe completarse en < 30 s desde la subida** (`14`, camino asíncrono — NO tiempo real). Ese presupuesto vive sobre la cola asíncrona cuyo motor lo decide **el ganador del concern (a) de C-03** (Postgres-como-cola por hipótesis A4, o RabbitMQ+Celery si C-03 lo promovió). Este change **no re-decide** ese motor: lo consume.

## What Changes

Implementa el Flujo 4 extremo a extremo y modela la entidad `Evidencia` con su cadena completa, el bucket WORM y el audit log inmutable:

- **Etapa 1 — Cliente** (zona no confiable): ante evento de severidad alta/crítica (RN-CC-01), captura clip de 5–10 s, calcula **SHA-256** + **firma HMAC con la clave de sesión rotativa**, pide URL firmada y **sube el binario directo al storage** (no pasa por el backend — RN-CC-04).
- **Etapa 2 — Backend al recibir**: valida la firma HMAC del cliente, **recalcula el hash** (2.ª verificación), persiste metadata de `Evidencia`, deposita el binario en **bucket WORM (Object Lock Compliance)** y escribe el **audit log** (append-only, hash encadenado). Encola la tarea asíncrona en la **cola ganadora de C-03**.
- **Etapa 3 — Worker asíncrono** (cola ganadora de C-03): re-descarga el clip, **3.ª verificación de hash**, **firma con la clave maestra asimétrica (RSA-2048 / Ed25519)** gestionada vía Vault.
- **Etapa 4 — Re-inferencia server-side firmada**: corre el modelo sobre el clip exacto y **firma el output** con la clave del backend (la versión confiable del análisis, no la del cliente).
- **Detección de manipulación**: si el hash recalculado no coincide en **cualquier** etapa → evento crítico **"evidencia corrupta o manipulada"** (RN-CC-03), persistido y propagado.
- **SLO**: re-inferencia + firma final **p99 < 30 s desde la subida** (`14`).

**Decisiones consumidas de C-03 (no se re-deciden aquí)**:
- Motor de la cola asíncrona = **ganador del concern (a)** de C-03 (hipótesis A4: Postgres-como-cola `SKIP LOCKED`+pg-boss; alternativa SAD: RabbitMQ quorum + Celery).
- El acceso a la evidencia detrás de un puerto de mensajería abstracto (Clean/Hexagonal) para que el motor sea sustituible sin tocar el dominio.

**BREAKING**: ninguno hacia atrás (no hay sistema previo). Hacia adelante, **habilita C-18** (verificación de cadena en apelación) que consume el certificado de la cadena de firmas producida aquí.

## Capabilities

> Estas capabilities modelan **comportamiento de producción verificable**: cada SHALL se prueba con un test (cadena de 4 firmas, inmutabilidad WORM, detección de hash divergente, audit log append-only, latencia de firma).

### New Capabilities

- `evidence-capture-upload`: captura del clip ante evento severo, hash SHA-256 + firma HMAC de sesión en el cliente, y upload directo a storage por URL firmada (la etapa 1 de la cadena, en zona no confiable).
- `evidence-custody-chain`: la cadena de custodia criptográfica de 4 etapas acumulativas (cliente HMAC → backend re-hash → worker firma maestra RSA/Ed25519 → re-inferencia server-side firmada), incluyendo la detección de hash divergente como evento crítico.
- `evidence-worm-storage`: depósito del binario en bucket WORM (Object Lock modo Compliance) inmutable durante la retención, y descarga vía URL firmada con expiración.
- `evidence-audit-log`: el audit log append-only con hashes encadenados que registra cada operación sobre la evidencia (depósito, acceso, firma) de forma inmutable y verificable.

### Modified Capabilities

<!-- Ninguna spec de dominio previa en openspec/specs/ que este change modifique. C-10 aún no produjo specs archivadas; la dependencia es de implementación (canal de eventos), no de spec a modificar. -->

(Ninguna — este change agrega capacidades nuevas; no modifica requisitos de capacidades ya especificadas en `openspec/specs/`.)

## Impact

- **Habilita**: C-18 (`verificacion-cadena-apelacion`) — consume el certificado de verificación de la cadena de firmas que esta capacidad produce.
- **Dependencias entrantes**: `C-10` (canal de eventos + persistencia en TimescaleDB + ganador de transporte de C-03 — provee el disparo "evento severo" y el fan-out del evento crítico de manipulación) y, transitivamente, `C-03` (ganador del concern (a) = motor de la cola asíncrona del worker).
- **Decisiones que consume** (de C-03): motor de cola asíncrona del concern (a). Si C-03 conservó Postgres-como-cola, el worker lee de Postgres (`SKIP LOCKED`+pg-boss); si C-03 promovió RabbitMQ+Celery, el worker es un consumer de RabbitMQ. **El change se implementa contra un puerto de mensajería abstracto** y selecciona el adaptador del ganador.
- **Actores/sistemas afectados**: estudiante (cliente que captura y firma), backend (verificador zero-trust), worker (firma maestra + re-inferencia), storage WORM (MinIO/S3 con Object Lock), Vault (clave maestra). Revisor/perito downstream (consumen la evidencia y su certificado).
- **Datos**: instancia la entidad `Evidencia` (hashes, firmas, uri_bucket, output_reinferencia) y el `Audit log` append-only del `04_modelo_de_datos.md`.
- **Riesgo principal**: una firma maestra mal gestionada (clave filtrada, rotación rota) invalida toda la evidencia firmada con ella. Mitigación: Vault + rotación anual con archivo seguro de claves previas (`08` §Seguridad).
- **SLO comprometido**: re-inferencia + firma final < 30 s al pico, medido contra la cola ganadora de C-03.
