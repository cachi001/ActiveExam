# Migraciones Alembic — convencion del proyecto

## Conexion por entorno (twelve-factor)

La URL de la base NO se hardcodea en `alembic.ini`. `env.py` la toma de
`DATABASE_URL` (inyectada via Vault/tmpfs). Si falta, Alembic falla explicito.

## Convencion: migraciones destructivas en DOS PASOS (expand/contract)

Regla dura del proyecto (KB `08` + DD): **ningun cambio destructivo se hace en
una sola migracion**. Toda eliminacion o renombrado de columna/tabla se parte:

1. **EXPAND** — agrega lo nuevo manteniendo compatibilidad con lo viejo. Se
   deploya con el codigo que aun lee/escribe el esquema anterior.
2. **CONTRACT** — elimina lo viejo, recien cuando ninguna instancia en produccion
   lo usa.

Esto evita downtime y perdida de datos durante despliegues rolling. El template
`script.py.mako` recuerda esta convencion en cada migracion nueva.

## Migracion 001 — `0001_enable_timescaledb.py`

- `upgrade`: `CREATE EXTENSION IF NOT EXISTS timescaledb`. **Sin tablas de
  dominio** (esas son C-05).
- `downgrade`: `DROP EXTENSION IF EXISTS timescaledb`. Reversible sin perdida
  porque el esquema esta vacio.

Deja la extension lista para que C-05 cree la hypertable de eventos.

## Migracion 002 — `0002_core_models.py` (C-05)

Materializa el **modelo de datos del dominio** y sus invariantes EN EL MOTOR
(sobre la 001):

- **Tablas transaccionales** (`04`): `usuario`, `examen`, `sesion`, `asignacion`
  (union *—* proctor↔examen), `consentimiento`, `embedding`, `evidencia`,
  `caso_disciplinario`, con sus FKs y la convencion de nombres de constraints.
- **Enum de Sesion**: tipo nativo `estado_sesion`
  (`iniciada/activa/finalizada/flaggeada/cerrada`) -> la base **rechaza** estados
  fuera del enum (D3).
- **Audit log append-only** (DD-07): `audit_log` con `hash_prev`/`hash_self`,
  trigger `trg_audit_log_no_mutacion` que **aborta UPDATE/DELETE** (D1) y trigger
  `trg_audit_log_encadenar` que encadena el hash al INSERT (D2). Usa `pgcrypto`
  (`digest(...)`).
- **Consentimiento inmutable** (D5): trigger `trg_consentimiento_no_mutacion`
  anti-UPDATE/DELETE.
- **Evento hypertable** (D4, `04` Evento): `create_hypertable` particionada por
  dia, indices `(session_id, timestamp)` y `(exam_id, timestamp)`, **compresion**
  (`add_compression_policy('evento', INTERVAL '7 days')`, chunks <7d sin comprimir)
  y **continuous aggregates base** (`cagg_eventos_sesion_min`, `cagg_score_sesion`,
  `cagg_sesiones_activas_examen`, `cagg_distribucion_tipo`).

**Downgrade en dos pasos** (convencion expand/contract): primero quita agregados,
policies, triggers, funciones, indices y la hypertable; luego dropea las tablas en
orden inverso de FK y el tipo enum. El esquema vuelve al estado post-001
(extension presente, sin tablas de dominio).

> Nota: la firma HMAC del Evento se modela como columna (`firma`), pero su
> VALIDACION de produccion es C-10; el cifrado del `embedding.vector_cifrado` lo
> opera infraestructura (KMS, `08`) — la 002 solo deja la columna `BYTEA`.

## Comandos de verificacion (requieren la DB del compose arriba — NO ejecutados aqui)

```bash
# Con DATABASE_URL exportada y Postgres/TimescaleDB arriba:
cd backend
alembic upgrade head      # aplica 001 + 002
alembic downgrade 0001    # revierte 002 en dos pasos (deja la 001 aplicada)
alembic downgrade base    # revierte 001: remueve la extension (esquema vacio)
alembic current           # muestra la revision aplicada

# Tests de invariantes en el motor (requieren la 002 aplicada):
RUN_STACK_TESTS=1 pytest tests/test_db_invariants.py

# Logica de dominio pura (NO requiere DB):
pytest tests/test_session_lifecycle.py tests/test_audit_hash_chain.py
```

Verificar manualmente la reversibilidad: `upgrade head` luego `downgrade base`
sobre una base limpia debe dejar la DB sin tablas de dominio ni extension, sin
errores. El criterio de salida de C-05 (desbloquea C-06): la 002 aplica, las
invariantes estan en el motor y los tests verdes.
