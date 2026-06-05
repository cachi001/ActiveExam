# Flujos Principales

Cada flujo se documenta extremo a extremo mostrando interacciones entre componentes.

## Flujo 0: Vista general del ciclo (extremo a extremo)

```
[PRE-EXAMEN]     Admin configura examen → asigna estudiantes → carga foto institucional → define parámetros
       │
[INGRESO]        Estudiante autentica (Keycloak) → chequeo de dispositivo → permisos cámara/mic/pantalla
       │
[BIOMETRÍA]      Foto (snapshot) + liveness → embedding facial → comparación 1:1 con foto institucional
       │                                              (3 fallos → escala a proctor humano)
       ▼
[MONITOREO]      MediaPipe en navegador (rostro/mirada/postura) ─┐
       │          Detector de pestaña/foco/monitores      ├─► eventos estructurados ─► WS ─► backend
       │          Heartbeat firmado cada 5s ──────────────┘                                    │
       │                                                                                       ▼
[SCORING]        backend valida firma → persiste en TimescaleDB → calcula score incremental → fan-out a paneles
       │
[EVIDENCIA]      evento severo | heartbeat periódico → screenshot (frame único) → hash+firma cliente → upload directo a storage (URL firmada)
       │                            → re-hash+firma backend → re-inferencia ESTÁTICA server-side (sobre el frame) → firma maestra
       │          [C-24, DD-24-01/02/03: screenshot reemplaza al clip 5-10s; tradeoff L2.5 aceptado — sin re-inferencia temporal]
       ▼
[POST-EXAMEN]    cierre de sesión → score final → cola de revisión (si supera umbral) → liberación de clave
       │
[REVISIÓN HUMANA] revisor abre sesión (acceso auditado) → decide: descartar | escalar | derivar a disciplina
```

## Flujo 1: Autenticación y chequeo de dispositivo

**Disparador**: el estudiante abre el examen habilitado.
**Actor**: estudiante.

**Pasos**:
1. El estudiante ingresa con credenciales institucionales (federación SAML/LDAP vía Keycloak).
2. Keycloak emite un token JWT; el estudiante es redirigido al examen.
3. La app valida el perfil mínimo del dispositivo (cámara, micrófono, capacidad de cómputo, navegador compatible).
4. Si cumple, continúa; si no, comunica el problema con instrucciones claras o escala a un proctor.

**Casos de error**:
- Dispositivo insuficiente → instrucciones claras o escalación a proctor (nunca abort silencioso).
- JWT inválido/expirado → rechazo; el cliente refresca el token vía `/api/v1/auth/refresh`.

## Flujo 2: Consentimiento + verificación biométrica de identidad

**Disparador**: dispositivo validado.
**Actor**: estudiante; backend; DB de embeddings.

**Pasos**:
1. Pantalla de consentimiento informado (lenguaje claro); el acuse se persiste con timestamp + hash.
2. Captura de foto (snapshot).
3. Liveness: parpadeo involuntario, micro-movimientos y profundidad 3D estimada por Face Mesh.
4. Cálculo del embedding facial (Face Mesh).
5. El cliente solicita el embedding de referencia (leído cifrado de la DB).
6. Comparación por distancia coseno contra el embedding precomputado.
7. Si distancia < umbral → el backend emite la clave de sesión rotativa → examen habilitado.

**Diagrama de secuencia**:
```
Cliente                              FastAPI                    DB(embedding ref)
  │ captura foto (snapshot)              │                            │
  │ liveness (blink, micro-mov, 3D)     │                            │
  │ calcula embedding (Face Mesh)       │                            │
  │── solicita embedding de referencia ►│── lee (cifrado) ──────────►│
  │◄── embedding ref ───────────────────│                            │
  │ distancia coseno < umbral ?         │                            │
  │   SÍ → solicita clave de sesión ───►│── emite clave rotativa ───►│
  │◄── clave de sesión ─────────────────│                            │
  │ examen habilitado                   │                            │
  │   NO → reintento (máx 2) → evento crítico → escala a proctor     │
```

**Casos de error**:
- Liveness/comparación falla → hasta 2 reintentos; al 3.º fallo evento crítico + escalación a proctor.
- Sin foto institucional de referencia → la verificación 1:1 no opera (dependencia de registro previo).

## Flujo 3: Monitoreo continuo y generación de eventos

**Disparador**: examen habilitado.
**Actor**: cliente (Web Worker); backend; TimescaleDB; paneles.

**Pasos**:
1. El Web Worker ejecuta MediaPipe (Face Detection, Face Mesh, Pose) sobre el feed local a 5–10 fps (2–5 fps Pose).
2. Un detector adicional analiza pestaña activa, foco de ventana y monitores múltiples.
3. Las reglas de transición de estado convierten señales continuas en eventos discretos con severidad.
4. Cada evento se guarda en el buffer IndexedDB y se envía por WebSocket; cada 5 s un heartbeat firmado con HMAC.
5. El backend valida cada firma, persiste en TimescaleDB, calcula score incremental y hace fan-out a los paneles.

**Casos de error**:
- Ruido instantáneo → filtrado por umbrales temporales (no genera evento).
- Dispositivo limitado → degradación graceful (baja Pose, luego Face Mesh; si insuficiente, escala a proctor).

## Flujo 4: Captura y firma de evidencia (cadena de custodia)

**Disparador**: evento de severidad alta/crítica.
**Actor**: cliente; FastAPI; Storage; cola/worker; DB.

**Diagrama de secuencia**:
```
Cliente        FastAPI        Storage(S3)     Cola/RabbitMQ  Worker        DB
  │ evento severo │               │              │            │            │
  │──hash+firma──►│               │              │            │            │
  │  presign URL  │──────────────►│              │            │            │
  │◄── URL ───────│               │              │            │            │
  │── PUT captura ───────────────►│              │            │            │
  │── notifica ──►│ valida firma  │              │            │            │
  │               │── audit log ──────────────────────────────────────────►│
  │               │── encola firma+reinferencia ►│            │            │
  │               │               │              │── tarea ──►│            │
  │               │               │◄── GET captura ────────────│            │
  │               │               │              │            │ re-hash    │
  │               │               │              │            │ firma maestra
  │               │               │              │            │── persiste ►│
  │◄── ack "recibido y validado" ─│              │            │            │
```

**Pasos**: (1) cliente hashea (SHA-256) + firma (HMAC clave de sesión); (2) pide URL firmada y sube la captura directa al storage; (3) backend valida firma, recalcula hash, persiste metadata, audit log, deposita en bucket WORM; (4) encola firma + re-inferencia; (5) worker re-descarga, 3.ª verificación de hash, firma con clave maestra (RSA-2048/Ed25519), re-inferencia opcional firmada.

**Casos de error**:
- Hash no coincide → evento crítico "evidencia corrupta o manipulada".
- Error de escritura en MinIO → la captura queda en buffer; reintento de subida.

## Flujo 5: Reconexión sin pérdida de eventos

**Disparador**: caída del WebSocket por red inestable.
**Actor**: cliente; FastAPI; TimescaleDB.

**Diagrama de secuencia**:
```
Cliente                         FastAPI                       TimescaleDB
  │  (WS cae por red inestable)    │                              │
  │  eventos → buffer IndexedDB    │                              │
  │  backoff exponencial + jitter  │                              │
  │── handshake(session_id, JWT, last_event_id) ─►│              │
  │                                │── query eventos > last_id ──►│
  │                                │◄── eventos faltantes ────────│
  │◄── reenvía + reanuda ──────────│                              │
  │  drena buffer en orden ───────►│  (dedup por event_id)        │
  │                                │  exactly-once lógico         │
```

**Casos de error**:
- Corte > 5 min → evento crítico al reconectar.
- Eventos duplicados → deduplicación por `event_id`.

## Flujo 6: Cierre, scoring final y encolado a revisión

**Disparador**: el estudiante envía respuestas / finaliza la sesión (`/sessions/{id}/finish`).
**Actor**: estudiante; tarea asíncrona; cola de revisión.

**Pasos**:
1. Cierre de sesión; se libera la clave de sesión.
2. Una tarea asíncrona consolida métricas y calcula el score final.
3. Si el score supera el umbral institucional, la sesión entra a la cola de revisión (ordenada por score descendente).
4. Si no, la sesión se archiva.

```
EVENTOS (continuos) → SCORE INCREMENTAL (al minuto, continuous aggregate)
       │ al cierre
       ▼
SCORE FINAL → ¿supera umbral?
   NO → sesión archivada
   SÍ → COLA DE REVISIÓN HUMANA (ordenada por score, mayor primero)
              ▼
       REVISOR decide: descartar | escalar | derivar a disciplina
```

## Flujo 7: Revisión humana asíncrona

**Disparador**: sesión en cola de revisión.
**Actor**: revisor académico.

**Pasos**:
1. **Encolado**: sesiones que superan el umbral, ordenadas por score descendente.
2. **Asignación**: el revisor toma una sesión de su jurisdicción; cada apertura se registra en el audit log con propósito declarado.
3. **Contexto completo**: línea de tiempo de eventos, capturas firmadas, observaciones del proctor, output de re-inferencia, audit log de accesos previos.
4. **Decisión**: descartar (falso positivo) | escalar (investigación) | derivar a proceso disciplinario formal.
5. **Trazabilidad**: la decisión y su fundamento se persisten vinculados a la evidencia mediante referencias inmutables.

**Casos de error**:
- Backlog acumulado → riesgo operativo: el sistema falla en su propósito si la institución no sostiene la capacidad de revisión.

## Flujo 8: Verificación de evidencia en apelación (UC-06)

**Disparador**: caso disciplinario apelado que cuestiona la evidencia.
**Actor**: institución / perito externo.

**Pasos**:
1. Se invoca `POST /api/v1/evidence/{id}/verify-chain`.
2. El sistema genera un certificado de verificación de la cadena de firmas (cliente → backend → worker/clave maestra → re-inferencia).
3. Un perito externo valida la cadena independientemente.

**Casos de error**:
- Cadena rota / hash no validable → la evidencia no se sostiene; queda registrado.

## Flujo 9: Ejercicio de derecho al olvido (UC-05)

**Disparador**: el estudiante solicita eliminación (`POST /api/v1/dsr/{type}`).
**Actor**: estudiante; DPO.

**Pasos**:
1. El sistema verifica que el estudiante no tenga casos abiertos (holds).
2. Si no hay holds: elimina binarios y embeddings, anonimiza registros, conserva un residual sin datos personales.
3. Responde en plazo legal; la operación es verificable en auditoría.

**Casos de error**:
- Caso abierto (hold) → la eliminación se difiere hasta cerrar el caso.
