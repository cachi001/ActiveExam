# Spec — evidence-custody-chain

> La cadena de custodia criptográfica de **4 etapas acumulativas** (RN-CC-02, DD-07): cliente HMAC → backend re-hash → worker firma maestra RSA/Ed25519 → re-inferencia server-side firmada. Incluye la detección de hash divergente y el SLO de firma < 30 s. La etapa asíncrona usa el **ganador de cola de C-03** detrás de un puerto abstracto.

## ADDED Requirements

### Requirement: Etapa 2 — verificación de firma y re-hash en el backend
El backend SHALL, al recibir la notificación de evidencia, validar la **firma HMAC del cliente**, **recalcular el hash** del binario (2.ª verificación) y persistir la metadata de `Evidencia` solo si la firma es válida y el hash coincide.

#### Scenario: Backend valida firma y re-hashea
- **WHEN** el backend recibe la notificación de un clip subido con su `hash_cliente` y `firma_cliente`
- **THEN** valida la firma HMAC contra la clave de sesión, recalcula `hash_backend = SHA-256(clip)` y, si coincide con `hash_cliente`, persiste la `Evidencia` con ambos hashes

### Requirement: Etapa 3 — firma maestra asimétrica en el worker
Un worker asíncrono, consumiendo de la **cola ganadora de C-03** detrás de un puerto `JobQueuePort`, SHALL re-descargar el clip, realizar la **3.ª verificación de hash** y **firmar con la clave maestra asimétrica (RSA-2048 / Ed25519)** gestionada vía Vault.

#### Scenario: Worker re-verifica y aplica firma maestra
- **WHEN** la tarea de firma es tomada por el worker desde la cola
- **THEN** el worker re-descarga el clip, recalcula el hash y lo compara con `hash_backend`, y si coincide aplica `firma_maestra` con la clave maestra asimétrica de Vault

#### Scenario: El motor de la cola es el ganador de C-03 vía puerto abstracto
- **WHEN** se despliega el worker
- **THEN** consume de la cola a través de `JobQueuePort`, cuyo adaptador concreto es el ganador del concern (a) de C-03 (Postgres-como-cola o RabbitMQ+Celery), sin que el dominio de la cadena dependa del motor

### Requirement: Etapa 4 — re-inferencia server-side firmada
El worker SHALL ejecutar la **re-inferencia server-side** sobre el clip exacto y **firmar el output** del modelo con la clave del backend, persistiéndolo como `output_reinferencia` (la versión confiable del análisis, no la del cliente — RN-GLB-01).

#### Scenario: Output de re-inferencia firmado y persistido
- **WHEN** el worker completa la firma maestra
- **THEN** corre el modelo server-side sobre el clip, firma el output y lo persiste como `output_reinferencia` firmado, vinculado a la `Evidencia`

### Requirement: Firmas acumulativas, no reemplazadas
La `Evidencia` SHALL conservar las cuatro etapas de forma **acumulativa** (`hash_cliente`, `firma_cliente`, `hash_backend`, `firma_maestra`, `output_reinferencia` firmado); ninguna etapa sobrescribe a la anterior (RN-CC-02).

#### Scenario: Las cuatro firmas coexisten en la evidencia
- **WHEN** la cadena se completa
- **THEN** la `Evidencia` contiene los cuatro eslabones criptográficos simultáneamente, permitiendo a un perito reconstruir cada handoff

### Requirement: Detección de manipulación — hash divergente es evento crítico
Si el hash recalculado **no coincide en cualquier etapa**, el sistema SHALL generar un evento crítico **"evidencia corrupta o manipulada"** (RN-CC-03), persistirlo y propagarlo al panel; la manipulación NO se descarta en silencio.

#### Scenario: Hash divergente en el backend
- **WHEN** el `hash_backend` recalculado no coincide con el `hash_cliente`
- **THEN** se genera y persiste un evento crítico "evidencia corrupta o manipulada" y se propaga al canal de eventos

#### Scenario: Hash divergente en el worker
- **WHEN** el hash re-verificado por el worker no coincide con `hash_backend`
- **THEN** se genera el mismo evento crítico de manipulación, registrado y propagado

### Requirement: SLO de re-inferencia + firma final
El ciclo etapa 2 → etapa 4 (re-inferencia + firma maestra) SHALL completarse en **p99 < 30 s desde la subida** del clip, medido en Prometheus al pico (`14`); este es un camino **asíncrono**, no tiempo real.

#### Scenario: Firma final dentro del presupuesto
- **WHEN** un clip se sube al pico de carga
- **THEN** la latencia medida desde la subida hasta el output de re-inferencia firmado es p99 < 30 s
