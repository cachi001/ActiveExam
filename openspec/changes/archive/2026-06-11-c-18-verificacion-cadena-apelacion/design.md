# Design — C-18 `verificacion-cadena-apelacion`

## Context

El proyecto Proctoring (React + FastAPI + PostgreSQL/TimescaleDB + Keycloak + MinIO/S3 WORM, backend Clean/Hexagonal, NFR 1.000 sostenido / ~2.100 pico) construye la cadena de custodia en C-12 con cuatro etapas criptográficas acumulativas (RN-CC-02). Este change implementa el endpoint que la verifica en apelación (UC-06, Flujo 8) y produce un certificado que un perito externo valida de forma independiente (DD-07).

**Constraints:**
- La evidencia es **WORM** (Object Lock Compliance): la verificación es de **solo lectura**; nunca muta la evidencia ni la cadena.
- Las cuatro etapas: (1) cliente SHA-256 + HMAC con clave de sesión rotativa; (2) backend re-hash + firma; (3) worker firma maestra asimétrica RSA-2048 / Ed25519; (4) re-inferencia firmada sobre el clip exacto (RN-CC-02).
- La **firma maestra es asimétrica**: la clave pública se puede entregar al perito para verificación independiente sin exponer la clave privada.
- El audit log es append-only con hashes encadenados; la verificación se registra agregando entradas.
- El sistema NUNCA sanciona automáticamente (L2.5): `verify-chain` informa, no decide.

**Stakeholders:** institución, perito externo, coordinador disciplinario, auditor.

## Goals / Non-Goals

**Goals:**
- Exponer `POST /api/v1/evidence/{id}/verify-chain` que re-verifica las 4 etapas y emite un certificado con el resultado por etapa.
- Hacer el certificado **independientemente verificable** por un perito externo (hashes + firmas + claves públicas).
- Detectar cadena rota, declarar que la evidencia no se sostiene y registrarlo en el audit log.

**Non-Goals:**
- NO construir la cadena de custodia ni la firma/re-inferencia (eso es C-12).
- NO decidir el resultado disciplinario: el certificado es insumo del proceso humano (L2.5).
- NO emitir juicio legal sobre la apelación; solo verifica la integridad criptográfica.
- NO re-descargar el binario para re-firmarlo: re-verifica las firmas/hashes ya persistidos.

## Decisions

### D1 — Verificación etapa por etapa, resultado acumulativo
**Decisión**: `verify-chain` valida secuencialmente: (1) `hash_cliente` + `firma_cliente` (HMAC, si la clave de sesión está disponible); (2) `hash_backend` recalculado vs persistido + firma backend; (3) `firma_maestra` contra la clave pública maestra; (4) coherencia del `output_reinferencia` firmado sobre el clip. El certificado reporta el estado de **cada** etapa, no solo un booleano global.
**Por qué**: un perito necesita saber **dónde** se rompe la cadena, no solo que se rompió; granularidad por etapa = defendibilidad.

### D2 — Certificado autoportante para verificación independiente
**Decisión**: el certificado incluye, por etapa: el hash, la firma, el algoritmo y la **clave pública** necesaria (la maestra para la etapa 3), más identificadores de la evidencia. El perito puede recomputar hashes y verificar firmas con herramientas estándar, sin llamar a la API.
**Por qué**: "verificable independientemente" (RN-CC-07, DD-07) exige que el certificado no dependa del sistema emisor para ser creído. La firma asimétrica lo permite (clave pública entregable).

### D3 — Cadena rota = evidencia no sostenida + registro
**Decisión**: si cualquier etapa falla (hash no coincide o firma no valida, RN-CC-03), el certificado marca la cadena como **rota**, indica la etapa de ruptura, declara que la evidencia **no se sostiene** y el sistema escribe el hecho en el audit log.
**Por qué**: Flujo 8 caso de error explícito. El sistema declara la ruptura en lugar de ocultarla; eso es lo que da credibilidad al resto de la evidencia.

### D4 — Verificación de solo lectura y trazable
**Decisión**: `verify-chain` no muta la evidencia (WORM) ni la cadena; cada invocación se registra en el audit log (actor, propósito=apelación, evidencia_id, timestamp, resultado), encadenada por hash.
**Por qué**: la integridad de la evidencia debe preservarse; la propia verificación debe ser auditable (quién verificó, cuándo, con qué resultado).

## Risks / Trade-offs

- **Riesgo**: la clave de sesión rotativa (etapa 1) puede no estar disponible al momento de la apelación. **Mitigación**: el certificado distingue etapas verificables de etapas con material no disponible; las etapas 2-4 (con clave maestra asimétrica) bastan para sostener la evidencia.
- **Riesgo**: exponer demasiado en el certificado podría filtrar PII del clip. **Mitigación**: el certificado contiene hashes/firmas/claves públicas, no el contenido del clip.
- **Trade-off**: re-verificar firmas vs re-descargar y re-firmar el binario. Se re-verifica lo persistido (más barato, no toca el WORM); re-descarga del binario es opcional y fuera de alcance aquí.

## Migration Plan

Endpoint nuevo de solo lectura sobre el modelo de Evidencia existente (C-12). Requiere acceso a la clave pública maestra para la verificación. Sin migración de datos.

## Open Questions

- Formato exacto del certificado (estructura JSON firmada vs documento) — a alinear con lo que un perito argentino acepta como prueba.
- Disponibilidad de la clave de sesión histórica para la etapa 1 en apelaciones tardías.
