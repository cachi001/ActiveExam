## Context

Ver `proposal.md` §Why para la motivación. Acá solo el estado actual que condiciona el enfoque.

**Superficie auditada** (rutas de `App.tsx`, roles `ACADEMICO`/`ADMIN`/`SUPERVISION_VIVO`/`COLA_REVISION`):

| Pantalla | Ruta | Endpoint(s) que la alimentan |
|---|---|---|
| Panel de administración | `/admin` | `GET /exam-content` · `GET /proctoring/sessions` · `GET /config/effective` |
| Estadísticas | `/admin/estadisticas` | `GET /stats/resumen` (+ `export.pdf` / `export.xlsx`) |
| Auditoría | `/admin/auditoria` | `GET /admin/audit-log` · `/audit-modulos` · `/audit-catalogo` (+ exports) |
| Exámenes | `/admin/examenes` | `GET /exam-content` (paginado, `q`/`materia_id`/`comision_id`) |
| Notas | `/admin/notas` | cascada materias→comisiones→exámenes + `GET /exam-content/{id}/resultados` |
| Resultados de examen | `/admin/examenes/:id/resultados` | `GET /exam-content/{id}/resultados` · `PATCH .../archivar` · `POST .../sincronizar-moodle` |
| Materias y comisiones | `/admin/materias` | CRUD `exam-content/materias` · `/comisiones` |
| Usuarios | `/admin/usuarios` | `GET/POST/PUT/DELETE /users` + `POST /users/{id}/reactivar` |
| Registro de sesiones | `/admin/proctoring-sessions` | `GET /proctoring/sessions/registro` |
| Cola de revisión | `/admin/cola-revision` | `GET /proctoring/sessions` + `enriquecerYFiltrar` (cliente) |

**Restricciones que condicionan el diseño:**

1. El proyecto ya tiene **tres convenciones de "baja"** conviviendo, cada una con su razón: `eliminado_en TIMESTAMPTZ NULL` (usuario, sesión, embedding, foto de referencia), `activa BOOLEAN` (materia, comisión — es un *freeze* reversible de dictado, no una baja), y `archivado BOOLEAN` (filas de resultado — soft-hide de intentos duplicados). `examen_contenido` no tiene ninguna.
2. `materia` y `comision` sí tienen `DELETE`, pero **hard-delete condicionado a estar 100% vacías** (409 `materia_no_vacia` si no). Ese camino es inservible para un examen: un examen con sesiones rendidas nunca está vacío, y esas sesiones son evidencia que no se puede tocar (regla dura #6/#7).
3. `statCatalog.ts` ya existe como **fuente única** de label/ícono/tono por métrica, con su propio comentario explicando el problema que cierra. La deriva del Dashboard no es falta de mecanismo: es un consumidor que lo esquiva.
4. `main_activeexam.py` es el entrypoint real. El router `/api/v1/exams` (ExamConfig) **no está montado**; cualquier endpoint que se agregue ahí es código muerto.

## Goals / Non-Goals

**Goals:**
- Que una métrica con el mismo nombre cuente lo mismo en toda la superficie de administración, y que el criterio esté **declarado** (no inferible leyendo tres archivos).
- Que dar de baja un examen sea una operación de producto, no una consulta SQL contra producción.
- Dejar por escrito qué se verificó y resultó **correcto**, para que no se "arregle" después (Bloque C del proposal).

**Non-Goals:**
- **No** se rediseña ninguna pantalla ni se agrega ninguna métrica nueva. Si un número está bien, se lo deja como está.
- **No** se toca el motor de scoring, el umbral vivo, ni la semántica de riesgo (L2.5: prioriza, nunca sanciona).
- **No** se cambia el modelo de acceso por comisión (F-08 queda fuera, ver D5).
- **No** se unifican las tres convenciones de baja del proyecto en una sola. Cada una tiene su razón; esta auditoría solo llena el hueco de `examen_contenido`.

## Decisions

### D1 — `eliminado_en` para `examen_contenido`, no `activa` ni hard-delete

**Elegido:** columna `eliminado_en TIMESTAMPTZ NULL` (`NULL` = activo).

**Alternativas descartadas:**
- **`activa BOOLEAN`, como materia/comisión.** Ese flag es un *freeze de dictado* reversible y esperado ("esta comisión no se dicta este cuatrimestre"), no una baja. Un examen dado de baja es un error del catálogo que se quiere sacar de la vista; semántica distinta, y `activa` no registra **cuándo**.
- **Hard-delete condicionado a "vacío", como materia/comisión.** Inservible: el caso real que motivó el change (examen con datos asociados) devolvería 409 y volveríamos al SQL manual.
- **Hard-delete con cascada.** Prohibido: destruiría sesiones y evidencia (reglas duras #6/#7).

**Referencia de implementación:** `DELETE /users/{id}` + `POST /users/{id}/reactivar` + `GET /users?estado=activo|inactivo|todos` en `app/presentation/api/v1/users/router.py` ya implementan el patrón entero (soft-delete, reactivación, filtro tri-estado, auditoría, 404 si ya está de baja). Se copia esa forma; **no se inventa nada**.

### D2 — La baja del examen es administrativa: no propaga a la evidencia

Un examen dado de baja **sigue teniendo** sus sesiones, eventos, capturas, notas y decisiones de revisión, y siguen siendo consultables por id. La baja solo lo saca de los **listados** y de los **conteos de inventario**. Consecuencia deliberada y explícita: `total_sesiones` de Estadísticas **no** cae al dar de baja un examen — se rindió, existió, y esa actividad es un hecho histórico. Solo cae `total_examenes` (inventario vigente). Esto se declara en la spec para que no se lea después como una incoherencia nueva.

### D3 — "Entra a la Cola de revisión" tiene UNA definición

Definición canónica: **una sesión entra a la Cola de revisión si tiene un examen real vinculado (`examen_contenido_id IS NOT NULL`) y su `score >= umbral_cola_revision` vivo.**

Es la definición que la Cola ya aplica de hecho (`enriquecerYFiltrar`), y la que Estadísticas ya usa server-side (`_session_conditions`). Se alinea a los dos consumidores que hoy divergen:
- **Dashboard**: aplica el filtro de examen vinculado antes de contar (hoy no lo hace).
- **Registro de sesiones**: su tarjeta `en_cola_revision` cuenta hoy sobre sesiones **finalizadas incluyendo diagnóstico**. El listado de esa pantalla legítimamente muestra sesiones de diagnóstico (su ayuda dice que desde ahí se borran) — así que **no se cambia el listado**; se cambia el **agregado** para que cuente solo lo que realmente entra a la cola.

Nota sobre el resto del gap: el Dashboard cuenta sesiones **de cualquier estado** y Registro cuenta solo **finalizadas**. Eso es correcto y distinto a propósito (una es "actividad total", otra es "historial cerrado"); lo que se corrige es que ambas tarjetas lo digan con el vocabulario de `statCatalog` (D4) en vez de que dos "Sesiones" idénticas signifiquen cosas distintas.

### D4 — El vocabulario de métricas se consume, no se reescribe

Toda `StatCard` de la superficie de administración SHALL construirse con `statProps(key, value, subOverride?)`. Un label/ícono/tono hardcodeado en una pantalla es un defecto, no una decisión de estilo. Si una métrica no existe en `STAT_META`, se agrega **ahí** y se consume. El `sub` (scope) sí puede overridearse — es el único grado de libertad que el catálogo concede a propósito.

### D5 — F-08 (scoping de lecturas) no se toca en este change

El desbalance está confirmado y documentado: todas las **escrituras** del router académico llaman a `_exigir_pertenencia*`, y cuatro **lecturas** no. Pero decidir si un tutor debe poder leer resultados de comisiones que no dicta es una decisión de política institucional sobre acceso a datos de alumnos → **gobierno CRÍTICO**, análisis sin código sin aprobación explícita. Meterlo acá, además, mezclaría un cambio de RBAC con una auditoría de números y volvería el diff irrevisable. Se recomienda `c-79-scoping-lectura-panel-academico`.

### D6 — `archivado` pasa a tri-estado en la query string

`GET /{examen_id}/resultados` cambia `archivado: bool = False` por `archivado: str = "false"` con valores `"false"` (default, solo no archivadas) | `"true"` (solo archivadas) | `"todas"`. El servicio subyacente (`listar_resultados_examen`) **ya soporta** `archivado=None` = sin filtro; el único bloqueo era el tipado del router. El checkbox "Mostrar archivadas" pasa a mandar `"todas"`, que es lo que su etiqueta promete. Se conserva `"true"` como opción del contrato (un caso legítimo: "quiero ver solo lo archivado") aunque hoy ninguna pantalla lo use.

**Alternativa descartada:** renombrar el checkbox a "Ver solo archivadas" y no tocar el backend. Es más barato, pero deja al usuario sin forma de ver el conjunto completo — que es lo que realmente necesita quien está buscando un intento que alguien archivó.

### D7 — Las políticas de intentos ordenan por `creada_en`

`_aplicar_politica` usa `min/max` sobre `session_id` para `PRIMERO`/`ULTIMO`. Los ids son UUID v4 (`gen_random_uuid()`): **el orden es aleatorio**. `ProctoringSessionModel.creada_en` existe y ya se usa como eje temporal en Estadísticas (`por_dia`). Se proyecta `creada_en` en la fila de resultados y se ordena por ahí; desempate por `session_id` para que el resultado sea determinístico si dos sesiones comparten timestamp. Es el hallazgo con mayor daño real de todos: afecta **qué nota se escribe en Moodle**.

### D8 — Alcance del barrido de etiquetas

El barrido de F-07 se acota a: (a) claves de `*_META` del frontend que no correspondan a ningún valor que el backend emita, y (b) docstrings/comentarios que nombren roles eliminados en c-76 (`proctor`, `revisor`, `admin_examenes`, `docente` como rol). **No** es un rebautizo general de etiquetas: cambiar un texto que hoy es correcto rompe la memoria muscular de quien lo usa todos los días, sin ganancia.

### D9 — Publicar la nota es camino de ida

`mostrar_nota` gana el valor `nunca`, que pasa a ser el default. El orden permitido es
`nunca` → `al_cerrar` → `inmediata`, siempre hacia adelante. Esconder una nota que el
alumno ya vio no tiene efecto útil (ya la vio) y sí genera reclamos, así que la
transición inversa se bloquea en vez de dejarla disponible "por las dudas".

El enum solo no alcanza: el docente no razona en términos de enum, razona en "reviso y
publico". Por eso la acción visible es un botón **Publicar notas ahora**, y el enum queda
como el estado que ese botón mueve. Queda auditado quién publicó y cuándo.

### D10 — Los eventos de proctoring se ocultan al alumno por defecto

Decisión del dueño. Tiene una contra real que se acepta: mostrar los eventos disuade y
además le avisa al alumno que algo se detectó, lo que baja el reclamo posterior de "no
sabía". Se compensa con el consentimiento, que ya informa **que** se supervisa aunque no
se muestre el detalle evento por evento.

### D11 — PROFESOR supervisa pero no juzga

El rol nuevo se define por lo que **no** puede: emitir veredicto de integridad. Eso queda
exclusivo del COORDINADOR. Es la misma separación que ya justifica el rol TUTOR en
`domain/auth/roles.py`: quien pone la nota no decide si hubo fraude. Sin esa línea,
PROFESOR y COORDINADOR serían el mismo rol con dos nombres.

El COORDINADOR conserva exámenes, banco y estadísticas; al TUTOR se le sacan las tres.

### D12 — Un examen para varias comisiones se resuelve replicando

Se descartó la relación N:M entre examen y comisión. Replicar (N exámenes independientes,
uno por comisión) no toca el modelo de datos, deja el destino de la nota apuntando al
curso correcto de cada comisión, y no mezcla resultados.

El costo que se acepta: son exámenes separados, así que corregir una pregunta después de
crearlos obliga a corregirla N veces. La UI debe decirlo **antes** de crear, no después.

### D13 — El examen guarda la definición del sorteo, no su resultado

Hoy `sortear_por_categorias` elige un set una vez y lo congela: todos los alumnos rinden
lo mismo. El modelo de Moodle (verificado contra la documentación de la rama 5.x, que es
la que corre el campus) guarda la **condición** —categoría, subcategorías sí o no,
cantidad, etiqueta— y resuelve el set **al iniciar cada intento**.

Se adopta ese modelo. Implica que el set concreto se persiste en el intento, no en el
examen, para que la corrección y la revisión reconstruyan exactamente lo que rindió cada
alumno. Es el cambio más invasivo del change: toca corrección, revisión y cálculo de nota,
que hoy asumen un set único.

### D14 — El estado manual de la nota no puede pisar al confirmado

Sin API del campus, la nota se carga a mano y hoy queda "pendiente" para siempre. Se
habilita marcarla a mano, con dos reglas: queda registrado quién la marcó, y **no puede
sobrescribir** un estado confirmado por sincronización real. Una afirmación humana y una
confirmación del sistema no valen lo mismo y la UI debe distinguirlas.

### D15 — El registro LTI se automatiza sin perder la aprobación humana

La allowlist LTI es la raíz de confianza: cada fila es un Moodle habilitado a crear
cuentas. Que sea explícita está bien; que se cargue a mano copiando ids de un request no.

LTI 1.3 define el registro dinámico y el proyecto lo tiene **a medias**: publica la
configuración (`GET /lti/dynamic-registration`) pero no recibe ni persiste el registro. Se
completa, con la fila creándose en `activo=false` y un admin habilitándola. Un click en
vez de un POST a mano, sin perder la aprobación explícita.

### D16 — Un fallo de carga nunca se renderiza como estado vacío

La pantalla de materias mostraba "No hay materias registradas" ante un 401. Decirle a
alguien que sus datos no existen cuando en realidad el request falló puede llevarlo a
recrearlos y duplicar todo. Toda pantalla de listado distingue tres estados: cargando,
cargó y está vacío, y no pudo cargar. `DestinoMoodleSection.tsx` ya lo hace bien y es el
modelo a copiar.

## Risks / Trade-offs

- **La baja lógica se filtra a una consulta que no la contempla** (un `SELECT` sobre `examen_contenido` que alguien agregue después sin `eliminado_en IS NULL`) → mitigación: la exclusión vive en `ExamenContenidoSqlRepository.listar_paginado` y en `_contar_catalogo`, que son los dos únicos puntos de entrada al inventario; la spec lo declara como requisito y las tareas exigen un test por consumidor.
- **Cambiar un número que alguien ya usaba como referencia** (el Dashboard va a mostrar menos sesiones en cola tras excluir diagnóstico) → mitigación: el número nuevo es el que **siempre** mostró la Cola de revisión; se alinea hacia la pantalla que decide, no al revés. Vale mencionarlo al dueño en el checkpoint.
- **`archivado` tri-estado rompe un cliente que mande `archivado=true` esperando "incluir"** → mitigación: el único cliente es `ResultadosExamenPanel.tsx`, en este mismo repo y en este mismo change.
- **La auditoría encontró más de lo que arregla** (F-08) → mitigación: queda documentado en el proposal con recomendación de change propio, no enterrado en un comentario.
- **Riesgo de scope creep**: "auditar todo" invita a arreglar todo. Mitigación: el criterio de corte está en el proposal (contenido → se arregla acá; estructural o de política → se documenta y se recomienda change propio) y las tareas están cerradas sobre los hallazgos F-01…F-07.

## Migration Plan

1. **Migración `0083`** — `ADD COLUMN eliminado_en TIMESTAMPTZ NULL` sobre `examen_contenido`. Aditiva y nullable: las filas existentes quedan activas (`NULL`) sin backfill. **No** requiere el procedimiento destructivo de dos pasos.
2. **Backend antes que frontend**: el filtro `estado` del catálogo se despliega con default `activo`, que es el comportamiento actual observable. Un frontend viejo contra un backend nuevo sigue viendo exactamente lo que veía.
3. **Rollback**: `DROP COLUMN eliminado_en` es seguro mientras ningún examen esté dado de baja. Si ya los hay, el rollback **pierde la marca de baja** y esos exámenes reaparecen en los listados — no se pierde ningún dato de dominio. Se documenta en el downgrade de la migración.
4. **Verificación post-deploy**: dar de baja un examen de prueba, confirmar que desaparece de Exámenes / Dashboard / picker de Notas / `total_examenes`, que sus sesiones siguen consultables por id, y reactivarlo.
