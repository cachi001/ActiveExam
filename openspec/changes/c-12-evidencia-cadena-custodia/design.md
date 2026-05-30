# Design — C-12 `evidencia-cadena-custodia`

> Design técnico de producción de la **cadena de custodia criptográfica** (Flujo 4). El entregable es código de dominio con calidad de producción: 4 etapas de firma acumulativas, WORM inmutable, audit log append-only y SLO de firma < 30 s. Consume el **ganador de cola de C-03** detrás de un puerto abstracto.

## Context

El sistema Proctoring (React + FastAPI + PostgreSQL/TimescaleDB + MinIO/S3 + Vault) trata al **cliente como sensor no confiable** (RN-GLB-01, DD-02): la evidencia que sube el navegador es entrada hostil hasta probar lo contrario. La defendibilidad probatoria es el corazón del nivel L2.5 (DD-01): sin una cadena que un perito externo valide solo, no hay caso disciplinario sostenible (UC-06, Flujo 8).

**Constraints duros** (de la KB):
- **RN-CC-02**: 4 etapas criptográficas **acumulativas** — las firmas se encadenan, no se reemplazan.
- **RN-CC-03**: hash divergente en **cualquier** etapa → evento crítico "evidencia corrupta o manipulada".
- **RN-CC-04**: binarios suben **directo al storage** por URL firmada (no pasan por el backend).
- **RN-CC-05**: descarga de clip vía URL firmada que **expira en 15 min**.
- **RN-CC-06 / DD-07**: bucket WORM (Object Lock modo **Compliance**) — inmutable durante la retención, ni el propietario puede borrar.
- **RN-CC-08**: **cero pérdida** de evidencia; la firma y re-inferencia **no toleran pérdida** (durabilidad de la cola).
- **Audit log** (`04`): append-only, trigger rechaza UPDATE/DELETE, cada entrada incluye `hash_entrada_anterior` (cadena tipo blockchain rudimentaria), backups write-only separados.
- **SLO** (`14`): re-inferencia + firma final **< 30 s desde la subida** (asíncrono, NO tiempo real).

**Decisión heredada de C-03 (no se re-decide)**: el motor de la cola asíncrona de la etapa 3/4 es el **ganador del concern (a)** de C-03. Hipótesis A4 = Postgres-como-cola (`SKIP LOCKED` + pg-boss / `LISTEN/NOTIFY`); alternativa SAD = RabbitMQ quorum + Celery (DD-06). Este change se construye contra un **puerto de mensajería abstracto** y enchufa el adaptador del ganador.

**Stakeholders**: estudiante (captura/firma cliente), backend (verificador zero-trust), worker (firma maestra + re-inferencia), perito externo (valida la cadena en apelación — C-18), DPO/legal (defendibilidad).

## Goals / Non-Goals

**Goals:**
- Implementar las **4 etapas acumulativas** de firma con verificación de hash en las etapas 2, 3 (y output firmado en 4).
- Garantizar **WORM real** (Object Lock Compliance) y **audit log append-only** con hash encadenado verificable.
- Detectar manipulación (hash divergente en cualquier etapa) y emitir el **evento crítico** correspondiente.
- Cumplir el SLO de **re-inferencia + firma < 30 s** medido sobre la cola ganadora de C-03.
- Dejar la `Evidencia` consumible por C-18 (certificado de verificación de cadena para perito).

**Non-Goals:**
- NO re-decidir el motor de la cola (lo hizo C-03; aquí se consume detrás del puerto).
- NO implementar el `POST /evidence/{id}/verify-chain` ni el certificado para perito (eso es **C-18**, consume esta cadena).
- NO implementar el detector de eventos ni la captura de visión (eso es C-11); aquí solo se **reacciona** a un evento severo ya emitido por C-10/C-11.
- NO definir el canal de transporte ni el fan-out (C-10); aquí solo se **emite** el evento crítico de manipulación al canal existente.
- NO gestionar retención/holds del binario (eso es C-19); aquí se deposita inmutable, la política de retención la aplica otro change.

## Decisions

### D1 — Cadena acumulativa de 4 firmas, no firma única reemplazable
**Decisión**: persistir las cuatro firmas/hashes de forma acumulativa en `Evidencia` (`hash_cliente`, `firma_cliente`, `hash_backend`, `firma_maestra`, `output_reinferencia` firmado), nunca sobrescribir una etapa con la siguiente.
**Por qué**: RN-CC-02 — la defendibilidad ante un perito requiere reconstruir **cada eslabón**; una firma única no permite atribuir en qué punto se rompió la cadena ni quién la produjo.
**Alternativa considerada**: firma única server-side al final → no demuestra la integridad cliente→backend ni distingue manipulación en tránsito de manipulación en storage.

### D2 — Verificación de hash en cada handoff; divergencia = evento crítico, no descarte silencioso
**Decisión**: re-hashear en la etapa 2 (backend) y la etapa 3 (worker) y comparar contra el hash de la etapa anterior; cualquier divergencia genera el evento crítico "evidencia corrupta o manipulada" (RN-CC-03), persistido y propagado al panel.
**Por qué**: el cliente es hostil; un clip alterado debe **detectarse y registrarse**, no rechazarse en silencio (la manipulación es en sí misma señal forense relevante).
**Alternativa considerada**: confiar en el hash del cliente → viola zero-trust (RN-GLB-01).

### D3 — Upload directo a storage por URL firmada (el binario no toca el backend)
**Decisión**: el backend emite una **URL firmada de PUT**; el cliente sube el clip directo a MinIO/S3; el backend solo recibe la notificación + metadata + firma (RN-CC-04).
**Por qué**: subidas de ~2,8 GB/examen (`14`) pasando por el backend lo saturarían; el upload directo desacopla el ancho de banda de evidencia del cómputo del backend.
**Alternativa considerada**: proxy del binario por el backend → cuello de botella de I/O bajo carga de evidencia masiva.

### D4 — Bucket WORM en modo Compliance (no Governance)
**Decisión**: Object Lock en modo **Compliance** — ni siquiera una cuenta root puede borrar/modificar antes del retain-until.
**Por qué**: DD-07/RN-CC-06 — la defendibilidad exige que **nadie**, incluido el operador, pueda alterar la evidencia durante la retención. Governance permitiría override por un rol privilegiado, lo que abriría un vector de repudio.
**Alternativa considerada**: modo Governance → permite bypass con permiso especial; insuficiente para evidencia probatoria.

### D5 — Worker asíncrono detrás de un puerto de mensajería abstracto (ganador de C-03)
**Decisión**: la etapa 3/4 corre en un worker que consume de un **puerto `JobQueuePort`**; el adaptador concreto es el ganador del concern (a) de C-03 (Postgres-cola o RabbitMQ+Celery).
**Por qué**: Clean/Hexagonal (`08` §Patrones) — el dominio de la cadena de custodia no debe acoplarse al motor de cola; C-03 puede haber elegido cualquiera y un cambio futuro no debe tocar el dominio.
**Alternativa considerada**: acoplar el worker a Postgres o a Celery directo → rompe la sustituibilidad que C-03 dejó abierta.

### D6 — Clave maestra en Vault, firma asimétrica RSA-2048/Ed25519
**Decisión**: la clave maestra de firma vive en **Vault**, se inyecta en tmpfs efímero; la firma de la etapa 3 es asimétrica (RSA-2048 o Ed25519) para que un perito valide con la **clave pública** sin acceder a la privada.
**Por qué**: `08` §Seguridad — la verificación independiente del perito (C-18) requiere firma asimétrica; HMAC simétrico no permite validación por un tercero sin compartir el secreto.
**Alternativa considerada**: HMAC en todas las etapas → el perito necesitaría la clave secreta, rompiendo la verificación independiente.

### D7 — Audit log append-only con hash encadenado, verificado a diario
**Decisión**: cada operación sobre la evidencia escribe una entrada en `Audit log` con `hash_entrada_anterior`; un trigger de DB rechaza UPDATE/DELETE; la integridad de la cadena se valida a diario (`04`).
**Por qué**: la traza de accesos es parte de la defendibilidad (quién tocó qué y con qué propósito); un audit log mutable sería repudiable.
**Alternativa considerada**: log de aplicación plano → no inmutable, no encadenado, no defendible.

## Arquitectura de la cadena (4 etapas acumulativas)

```
ZONA NO CONFIABLE          │  ZONA CONFIABLE (servidor)
(cliente = sensor hostil)  │
                           │
[E1] evento severo         │
  ├─ clip 5–10 s           │
  ├─ SHA-256 (hash_cli)    │
  ├─ HMAC clave sesión     │
  └─ PUT directo ──────────┼──► STORAGE (presigned PUT URL)
       (URL firmada)       │
  notifica metadata+firma ─┼──► [E2] BACKEND (FastAPI)
                           │      ├─ valida firma HMAC cliente
                           │      ├─ RE-HASH (2ª verif.) ── ¿== hash_cli? ──NO──► EVENTO CRÍTICO
                           │      │                                              "evidencia corrupta/manipulada"
                           │      ├─ persiste Evidencia (metadata)
                           │      ├─ deposita binario en BUCKET WORM (Object Lock Compliance)
                           │      ├─ AUDIT LOG (append-only, hash_prev)
                           │      └─ encola tarea ──► JobQueuePort  [adaptador = ganador C-03]
                           │                              │
                           │      [E3] WORKER (consumer de la cola ganadora de C-03)
                           │      ├─ re-descarga clip (GET firmado)
                           │      ├─ 3ª VERIF. de hash ── ¿== hash_backend? ──NO──► EVENTO CRÍTICO
                           │      ├─ FIRMA MAESTRA (RSA-2048/Ed25519, clave de Vault)
                           │      │
                           │      [E4] RE-INFERENCIA server-side
                           │      ├─ corre modelo sobre el clip exacto
                           │      ├─ FIRMA el output (clave backend)
                           │      └─ persiste output_reinferencia firmado
                           │           ⏱ SLO: E2→E4 < 30 s desde la subida (p99)
```

> Las firmas son **acumulativas**: `Evidencia` termina con `hash_cliente`, `firma_cliente`, `hash_backend`, `firma_maestra`, `output_reinferencia` firmado. C-18 reconstruye esta cadena para el perito.

## Modelo de datos afectado

| Entidad | Atributos clave | Constraint |
|---------|-----------------|------------|
| `Evidencia` | `id`, `session_id`, `uri_bucket`, `hash_cliente`, `firma_cliente`, `hash_backend`, `firma_maestra`, `output_reinferencia`, metadatos | binario en bucket WORM (Object Lock Compliance); inmutable durante retención |
| `Audit log` | `id`, `actor`, `timestamp`, `IP`, `user-agent`, `acción`, `evidencia_id`, `propósito`, `hash_entrada_anterior` | append-only; trigger rechaza UPDATE/DELETE; hash encadenado |

> Estas entidades ya se modelaron en C-05 (`core-models`); este change las **usa** y materializa la lógica de la cadena sobre ellas.

## Risks / Trade-offs

- **[Clave maestra comprometida invalida toda la evidencia firmada]** → Mitigación: Vault + inyección en tmpfs; rotación anual con **archivo seguro de claves previas** para validar firmas históricas (`08` §Seguridad).
- **[SLO < 30 s no se sostiene al pico sobre el motor ganador de C-03]** → Mitigación: el puerto abstracto permite escalar workers; instrumentar p99 de E2→E4 en Prometheus; si Postgres-cola no sostiene, C-03 ya dejó documentada la ruta de evolución a RabbitMQ.
- **[Object Lock Compliance impide corregir un depósito erróneo]** → Trade-off **aceptado y deliberado**: la inmutabilidad es el valor; los errores se corrigen depositando una nueva evidencia, nunca alterando la existente.
- **[Re-inferencia server-side encarece el cómputo del worker]** → Mitigación: corre solo sobre clips de eventos severos (RN-CC-01), no sobre todo el stream; el grueso de la inferencia sigue en el cliente (DD-02).
- **[Manipulación detectada tarde si el worker se atrasa]** → Mitigación: la 2.ª verificación (etapa 2, síncrona en el backend) ya detecta la mayoría de las manipulaciones antes de encolar; la 3.ª es defensa en profundidad.

## Migration Plan

1. Crear/usar la entidad `Evidencia` y `Audit log` (de C-05) con sus constraints WORM/append-only.
2. Configurar el bucket de evidencia con **Object Lock modo Compliance** y retain-until por política.
3. Implementar la emisión de **URL firmada de PUT** y el endpoint de notificación (etapa 2).
4. Implementar la verificación de firma HMAC + re-hash síncrono + depósito WORM + audit log (etapa 2).
5. Implementar el **adaptador de cola del ganador de C-03** detrás de `JobQueuePort` y el worker (etapas 3/4).
6. Implementar firma maestra (Vault) + re-inferencia firmada; instrumentar p99 E2→E4.
7. Cablear la detección de hash divergente al **evento crítico** propagado por el canal de C-10.

**Rollback**: feature aislada tras puerto; si la cola del worker falla, los binarios ya están en WORM con su firma de etapa 2 (cliente+backend) — la cadena se completa al reprocesar (durabilidad RN-CC-08, sin pérdida).

## Open Questions

Cerradas por este change:
- ¿Cómo se materializan las 4 etapas acumulativas sobre `Evidencia`? → D1.
- ¿Qué motor de cola usa el worker? → el ganador de C-03, vía `JobQueuePort` (D5).

Fuera de alcance (otros changes):
- Certificado de verificación de cadena para perito + `POST /evidence/{id}/verify-chain` → **C-18**.
- Retención/holds del binario y archivado → **C-19**.
- Detección/captura del evento severo que dispara la evidencia → C-10/C-11.
