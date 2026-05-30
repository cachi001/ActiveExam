# Observabilidad, Operación y DevOps

Complementa `08_arquitectura_propuesta.md`. Operar sin observabilidad un sistema que sostiene 700 personas en una ventana crítica es "construir un avión sin instrumentos".

## Los tres pilares

- **Métricas**: Prometheus (tendencias y agregaciones); retención escalonada 30 días alta resolución, 1 año baja (vía Thanos).
- **Logs**: Loki (JSON estructurados con `trace_id` de correlación).
- **Trazas**: OpenTelemetry → Tempo/Jaeger; sampling preserva 100% de errores y latencias altas + 1% del tráfico normal.
- **Grafana**: interfaz unificada.

### Niveles de métricas
1. **Negocio**: sesiones activas, distribución de score, profundidad de la cola de revisión.
2. **Aplicación técnica**: latencias por percentil, profundidad de colas, hit rate de Redis.
3. **Infraestructura**: CPU, memoria, disco, red.
4. **Cliente agregado**: feeds degradados, dispositivos bajo perfil mínimo, versiones del cliente.

## SLIs / SLOs

| Indicador (SLI) | Objetivo (SLO) |
|-----------------|----------------|
| Disponibilidad en ventana de examen activo | 99,9% (~9 s en 3 h) |
| Disponibilidad fuera de ventana | 99,5% |
| Latencia de detección en cliente (p99) | sub-segundo |
| Latencia de propagación al panel (p99) | < 500 ms |
| Latencia de re-inferencia y firma final | < 30 s desde la subida |
| Pérdida de eventos confirmados / evidencia | cero |
| Recuperación | RTO 4 h (catastrófico) / 30 min (menor); RPO 5 min |

## Alertas, on-call y dashboards

- **Alertmanager** categoriza por severidad. Críticas (despiertan al on-call): instancias FastAPI caídas en examen activo, base primaria inalcanzable, queue crítica creciendo, tasa de errores HTTP excedida.
- Cada alerta tiene un **runbook** asociado.
- Dashboards predefinidos: ejecutivo, operacional (on-call), exámenes en curso, capacidad, seguridad.
- Cobertura 24×7 durante exámenes activos; canal dedicado en Sev 1.

## Gestión de incidentes

Ciclo: detección → declaración → mitigación → resolución → postmortem. Durante la mitigación: **restaurar primero, diagnosticar después**. Cada incidente Sev 1/2 genera una postmortem **blameless** en dos semanas; sus acciones entran al backlog con dueño y seguimiento.

### Runbooks principales

| Escenario (alerta) | Severidad | Mitigación inmediata |
|--------------------|-----------|----------------------|
| Instancia FastAPI no responde en examen | Sev 1 | Health check la saca del pool; clientes reconectan a otra; reiniciar/reemplazar |
| Base primaria con replicación detenida | Sev 1 | Verificar lag; promover réplica si el primario no recupera; restaurar replicación |
| Queue crítica creciendo | Sev 1-2 | Escalar workers de re-inferencia/firma; revisar DLX; identificar input corrupto |
| Redis con memoria crítica | Sev 2 | Verificar claves; ampliar memoria; revisar TTLs (el estado durable está en Postgres) |
| MinIO con error de escritura | Sev 1-2 | Verificar espacio/permisos; los clips quedan en buffer; reintentar subida |
| Keycloak no autentica | Sev 1 | Failover a 2.ª instancia; verificar federación con el IdP |
| Tasa elevada de tampering detectado | Sev 2 | Verificar falsos positivos por extensiones; ponderación humana; **no abortar exámenes** |
| Espacio en disco crítico | Sev 2 | Forzar archivado de chunks; limpiar logs antiguos; ampliar volumen |

## Capacity model (escala objetivo)

> **NFR de capacidad revisado (confirmado por el equipo, mayo 2026).** El objetivo operacional sostenido se eleva de **700 a 1.000 concurrentes**, manteniendo **~2.100 en pico multi-examen**. Esto es un *delta* sobre el supuesto original del discovery (700 — ver `SU-06` en `09_decisiones_y_supuestos.md`) y endurece el criterio de aceptación de la PoC de carga: **la prueba se clava al pico (~2.100 / ~5.000 inserts/s), no al sostenido.** El escalado lineal de inserts respecto del sostenido es una **Suposición** a validar en la PoC.

- **1.000 concurrentes** sostenido (objetivo operacional confirmado); **~2.100** en pico multi-examen.
- Heartbeats (cada 5 s) → ~200 inserts/s sostenido; eventos normales → ~1.000 inserts/s sostenido (**Suposición**: escala ~lineal desde los ~700/s estimados a 700 concurrentes); **picos hasta ~5.000 inserts/s** en ventana multi-examen.
- Un examen de 1 h produce 4–5 millones de filas → ~100–200 MB con compresión TimescaleDB.
- WebSockets: decenas a centenas de KB/s. Subidas de evidencia: ~2,8 GB por examen (4 clips/estudiante).
- Pico de autenticación al inicio: ~47 auth/min (cómodo para Keycloak en hardware modesto).

### Cuellos de botella y abordaje
| Cuello de botella | Abordaje |
|-------------------|----------|
| Inferencia de video | Resuelto por diseño: corre en el cliente |
| Inserts en la base de eventos | Hypertable TimescaleDB + compresión + agregados continuos |
| Pico de autenticación | Dentro de capacidad de Keycloak; biometría en cliente |
| Conexiones WS por instancia | Sticky sessions 200–250 WS/instancia + monitoreo de distribución |
| Subidas de evidencia pesadas | URLs firmadas: cliente sube directo al storage |

## CI/CD y entornos

- Paridad staging/producción (datos sintéticos en staging).
- Pipeline (GitLab CI o GitHub Actions): build (imágenes con tag inmutable por hash de commit), test, security scan (estático + imágenes + licencias), deploy automático a staging con smoke tests, deploy **manual** a producción con **aprobación de dos personas** y **solo fuera de ventanas de examen activo**.
- Versiones inmutables; rollback = redeploy de la imagen anterior.

## Backups, recuperación y DR

| Componente | Estrategia |
|-----------|-----------|
| PostgreSQL | Backup full diario + WAL streaming continuo → recuperación point-in-time. Retención 30 días / 1 año / 7 años (archivo) |
| MinIO (evidencia) | Replicación geográfica asíncrona cuando la infraestructura lo permite |
| Redis | No se respalda activamente (efímero); persistencia AOF para recuperar tras restart |
| RabbitMQ | Quorum queues para durabilidad; definiciones como código en el repo |

**RTO**: 4 h (catastrófico) / 30 min (menor). **RPO**: 5 min (WAL streaming + replicación geográfica). El plan de DR se prueba con ejercicios de tabletop.

## Topología inicial (Docker Compose) y migración a K8s

- 3–5 servidores: proxy/frontend (Nginx), 2–3 de aplicación (FastAPI), uno de workers, un nodo de datos pesado (Postgres primario + réplica + Redis + MinIO), un nodo para RabbitMQ/Keycloak/observabilidad.
- Restricciones: primaria y réplica en hosts distintos; RabbitMQ en ≥2 hosts; workers intensivos sin competir con la base por CPU.
- **Migración a Kubernetes** es evolución operacional, no rediseño (código twelve-factor): primero stateless (FastAPI, Celery/workers, Nginx), luego stateful vía operators (Patroni, RabbitMQ Cluster Operator, Redis Operator, MinIO Operator).

## Estrategia de calidad (pirámide de pruebas)

| Nivel | Qué cubre | Herramientas |
|-------|-----------|--------------|
| Unitarias | Lógica de dominio (reglas de transición, scoring, integridad) | pytest, aislamiento total |
| Integración | Repos↔Postgres, publisher↔Redis, productor↔RabbitMQ, cliente↔MinIO | Contenedores efímeros |
| Contrato | Esquema de eventos versionado, contratos de API, compatibilidad de migrations | Validación de schema |
| End-to-end | verificación → examen → evidencia → revisión | Automatización de navegador |
| Carga/estrés | 700 concurrentes, pico de inicio, inserts, latencias | Generadores de carga vs capacity model |
| Seguridad | SAST, escaneo de imágenes (Trivy/Grype), pentest ≥ anual | SAST en CI |
| Caos/resiliencia | Caída de instancia, corte de red, pérdida de nodo RabbitMQ | Inyección de fallos, ejercicios DR |

**Definition of Done**: cobertura dentro del umbral (foco dominio), cero vulnerabilidades críticas, performance dentro de NFR-03..05 bajo carga, observabilidad completa, runbooks, y **piloto controlado exitoso con examen real** antes de cerrar la fase.
