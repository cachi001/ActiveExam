# Relevamiento del 22/8/2026 — tasks pendientes

Pedido del dueño del proyecto tras probar el sistema. Cada task lleva: qué se pide,
dónde vive hoy en el código, qué falta y con qué se da por terminada. El nivel de
gobernanza indica cuánta autonomía tiene el agente que la implemente (CRITICO y ALTO
requieren aprobación humana antes de escribir código).

Orden sugerido de ataque al final del documento.

---

## T-01 · "Nunca" por defecto, y publicar las notas cuando el docente quiera

**Gobernanza**: MEDIA

**Definido por el dueño (22/8)**: así trabajan los docentes en Moodle. Al terminar el
examen la nota NO se muestra. El docente revisa, y recién cuando está conforme la
publica. Entonces no alcanza con agregar el valor `nunca`: hace falta la acción de
publicar.

Hoy `mostrar_nota` acepta solo dos valores y arranca en `al_cerrar`:

- `backend/app/presentation/api/v1/exam_content/schemas.py:713` → default `"al_cerrar"`
- `backend/app/presentation/api/v1/exam_content/schemas.py:749` → `Literal["al_cerrar", "inmediata"]`
- UI: `frontend/src/screens/exam-detail/ConfiguracionExamenSection.tsx:53`

**Falta**:

1. Tercer valor `nunca`, que pasa a ser el default de un examen nuevo y el recomendado
   en la UI.
2. Un botón **"Publicar notas ahora"** en el detalle del examen, que pase el examen a
   nota visible en el momento que el docente decida, sin tener que entender el enum.
   Es la acción que hoy no existe y es la que realmente pide el flujo de trabajo.
3. Que se vea el estado actual sin ambigüedad: "las notas están ocultas" o "publicadas
   el <fecha> por <persona>".

**Ojo con la regla de monotonía**: `backend/app/domain/exam_content/config.py:101-104`
restringe cómo puede cambiar `mostrar_nota` una vez que el examen tiene intentos (hoy
de `inmediata` no se puede retroceder). El orden natural con la definición nueva es
`nunca` → `al_cerrar` → `inmediata`, siempre hacia adelante: una vez que el alumno vio
la nota, esconderla de nuevo no tiene sentido y solo genera reclamos. Publicar es un
camino de ida, y la UI tiene que decirlo antes de confirmar.

**Terminada cuando**: un examen nuevo arranca en `nunca`, el botón de publicar funciona
y queda registrado en auditoría quién publicó y cuándo, la transición hacia atrás está
bloqueada con test, y la migración define en qué estado quedan los exámenes existentes.

---

## T-02 · El dashboard muestra según el rol

**Gobernanza**: ALTA (toca autorización)

**Definido por el dueño (22/8)**: al TUTOR se le sacan Estadísticas, Creación de
exámenes y Banco de preguntas. El COORDINADOR **conserva todo eso**.

Hoy el tutor ve el menú completo. Debería ver solo lo suyo.

- Menú: `frontend/src/ui/nav.ts` y `frontend/src/screens/AdminDashboard.tsx`
- Capacidades reales: `backend/app/domain/auth/capabilities.py`, `authorization.py`

**Importante**: esconder el ítem del menú NO alcanza. Cada endpoint tiene que rechazar
al tutor por capacidad, o sigue habiendo acceso escribiendo la URL a mano. El frontend
solo refleja lo que el backend ya niega.

**Terminada cuando**: el tutor no ve esos ítems, y además cada endpoint correspondiente
devuelve 403 para su rol, con test por endpoint.

---

## T-03 · Export de alumnos inscriptos por comisión (PDF y Excel)

**Gobernanza**: BAJA

Sirve para cruzar el listado contra Moodle y detectar diferencias de matrícula.

- Datos ya disponibles: `GET /exam-content/comisiones/{id}/alumnos`
  (`backend/app/presentation/api/v1/exam_content/catalog_router.py:1651`)

**Falta**: generar el archivo en los dos formatos y el botón en la pantalla de la
comisión. Definir qué columnas lleva (mínimo: apellido, nombre, usuario, email, fecha
de inscripción) para que el cruce con Moodle sea directo.

**Terminada cuando**: desde la comisión se bajan los dos archivos con los inscriptos
actuales y las columnas acordadas.

---

## T-04 · Varios tutores por comisión

**Gobernanza**: ALTA (toca autorización)

Referencia pedida: https://github.com/JuanCruzRobledo/active-ia-correcion-automatica

**Estado real**: esto ya está hecho en el working tree, sin commitear. Existen
`backend/app/infrastructure/persistence/models/comision_tutor.py`, la migración
`0086_c79_comision_tutor_materia_coordinador.py` y los métodos
`agregarTutorComision` / `quitarTutorComision` en `frontend/src/lib/apiAdmin/moodle.ts`.

**Falta**: cerrar c-79, commitearlo y desplegarlo. Queda pendiente además dropear la
columna vieja `docente_id` una vez que nada la lea.

**Terminada cuando**: está en `main`, se pueden asignar y quitar varios tutores desde
la UI, y `docente_id` ya no se usa.

---

## T-05 · Crear un examen para varias comisiones

**Gobernanza**: MEDIA

Hoy el examen apunta a UNA comisión: `comision_id` es una columna simple y nullable en
`backend/app/infrastructure/persistence/models/exam_content.py:318`.

**Definido por el dueño (22/8)**: **replicado por comisión**. Al crear el examen se
eligen N comisiones y se generan N exámenes independientes, uno por comisión, en vez de
un examen compartido.

Es la decisión barata y la correcta acá: el modelo de datos no cambia (`comision_id`
sigue siendo uno solo por examen), el destino de la nota en Moodle sigue siendo por
examen y cada comisión apunta a su curso, y los resultados no se mezclan. Lo único que
cambia es la pantalla de creación y una transacción que crea varios.

**Falta**: selección múltiple de comisiones en la creación, y crear los N exámenes en
una sola operación (todo o nada, no dejar la mitad creada si falla una). Definir cómo
se nombran para distinguirlos, probablemente sufijando la comisión.

**Consecuencia a asumir**: son exámenes separados. Editar el contenido de uno NO toca a
los otros. Si el docente corrige una pregunta después de crearlos, la corrige N veces.
Vale la pena decirlo en la UI al momento de crear, para que no sea una sorpresa.

**Terminada cuando**: se eligen varias comisiones al crear, quedan N exámenes con su
comisión y su destino de nota, y si falla la creación de uno no queda ninguno a medias.

---

## T-06 · Duplicar un examen

**Gobernanza**: BAJA

**Falta**: acción "Duplicar" en el listado y en el detalle, que cree un examen nuevo con
el mismo contenido y configuración, con el nombre sufijado como copia.

Definir qué NO se copia: intentos de alumnos, resultados, destino de Moodle (probable
que convenga NO copiarlo para no mandar notas al curso equivocado por olvido) y el
estado de publicación.

**Terminada cuando**: duplicar deja un examen editable e independiente del original, sin
arrastrar intentos ni resultados.

---

## T-07 · Rol PROFESOR

**Gobernanza**: CRITICA (auth)

Hoy los roles son cuatro: `ESTUDIANTE`, `TUTOR`, `COORDINADOR`, `ADMIN_SISTEMA`
(`backend/app/domain/auth/roles.py`). Varios roles viejos fueron eliminados a propósito
en c-76 y remapeados por migración, así que agregar uno nuevo no es solo sumar una línea
al enum.

**Permisos pedidos**: creación de exámenes, banco de preguntas, estadísticas, registro
de sesiones, supervisión en vivo.

**Definido por el dueño (22/8)**: el PROFESOR **no emite veredicto**. El veredicto de
integridad queda exclusivo del COORDINADOR.

Esto mantiene en pie la separación de diseño del proyecto: quien pone la nota no decide
si hubo fraude. El PROFESOR mira en vivo y ve el registro, pero la decisión disciplinaria
sigue siendo del coordinador.

**Mapa de capacidades resultante**:

| Capacidad | TUTOR | PROFESOR | COORDINADOR | ADMIN |
|---|---|---|---|---|
| Crear exámenes | no | sí | sí | sí |
| Banco de preguntas | no | sí | sí | sí |
| Estadísticas | no | sí | sí | sí |
| Registro de sesiones | solo las suyas | sí | sí | sí |
| Supervisión en vivo | solo las suyas | sí | sí | sí |
| Emitir veredicto | no | **no** | **sí** | sí |

Tabla cerrada por el dueño el 22/8: el COORDINADOR conserva todo, al TUTOR se le sacan
esas tres. La diferencia real entre PROFESOR y COORDINADOR queda siendo el veredicto.

**Terminada cuando**: existe el rol, tiene sus capacidades en `capabilities.py`, hay
migración, y hay test por endpoint de lo que puede y de lo que no, incluido un test que
confirme que PROFESOR recibe 403 al intentar emitir veredicto.

---

## T-08 · Filtros en Supervisión en vivo, con alcance por rol

**Gobernanza**: ALTA (toca autorización)

**Falta**: filtros de materia, comisión y examen para coordinador y profesor. El tutor no
elige: ve solo sus comisiones, sin poder ampliar el filtro.

**Terminada cuando**: el filtro existe para los roles amplios y el backend acota el
resultado del tutor a sus comisiones, aunque el request pida otra cosa.

---

## T-09 · Registro de sesiones acotado al tutor

**Gobernanza**: ALTA (toca autorización)

Mismo criterio que T-08: el tutor ve solo las sesiones de su comisión.

- Pantalla: `frontend/src/screens/ProctoringSessionDetail.tsx` y el listado de sesiones
- Backend: `backend/app/presentation/api/v1/proctoring/sessions/router.py`

**Terminada cuando**: el filtrado ocurre en la query del backend, no en el frontend, con
test que confirme que un tutor no ve la sesión de otra comisión.

---

## T-10 · Armado del examen como Moodle: preguntas aleatorias por alumno

**Gobernanza**: MEDIA (alta si se toca el cálculo de nota)

Es la task más grande del relevamiento y la que define el producto. Reúne lo que en la
primera versión de este documento estaban separados como T-10 y T-11.

### Cómo funciona en Moodle (investigado el 22/8/2026)

El campus corre **Moodle 5.2.2+ (Build 20260818)**, así que la referencia es el
comportamiento de la rama 5.x, no el de versiones viejas.

1. **El banco es un árbol de categorías y subcategorías.** El listado muestra tipo de
   pregunta, nombre, estado, versión y quién la creó, con filtros por categoría, por
   etiqueta y por texto.
2. **Cada pregunta tiene vista previa.** Se abre desde el banco y renderiza la pregunta
   tal como la va a ver el alumno, con su tipo, su puntaje, la respuesta correcta y la
   retroalimentación. Es lo que permite revisar un import antes de usarlo.
3. **Al armar el cuestionario hay dos formas de agregar**: elegir preguntas concretas
   del banco, o agregar **una pregunta aleatoria**.
4. **La pregunta aleatoria se configura con**: categoría, un checkbox para incluir las
   subcategorías, filtro opcional por etiqueta, y cantidad. Desde Moodle 4.3 el slot
   guarda la CONDICIÓN de filtro, no las preguntas concretas.
5. **El sorteo ocurre al iniciar cada intento, por alumno.** Dos alumnos del mismo
   cuestionario reciben preguntas distintas. Un reintento del mismo alumno recibe otras,
   si el pool alcanza.
6. **Nunca repite** una pregunta dentro del mismo intento, y no sortea una que ya esté
   puesta como pregunta fija del cuestionario.
7. **Si el pool es más chico que la cantidad pedida**, Moodle avisa: no completa con
   repetidas ni sortea de más.
8. **Cada slot aleatorio tiene su propio puntaje** y la pregunta que salga se reescala a
   ese puntaje, para que el examen valga lo mismo sin importar cuál tocó.
9. **La calificación máxima del cuestionario es independiente** de la suma de los
   puntajes de las preguntas: Moodle reescala el total contra ese máximo.

### Qué tenemos hoy

`POST /exam-content/{examen_id}/sortear-preguntas` (`catalog_router.py:2529` →
`repo.sortear_por_categorias`, `repositories/exam_content.py:484`) sortea N preguntas
por categoría **una sola vez**, las marca `seleccionada=true` en el examen, y ese set
queda fijo. Todos los alumnos rinden exactamente las mismas preguntas. Es un sorteo de
armado, no un sorteo de rendición.

Además la selección en el detalle del examen es manual y no muestra qué se está
eligiendo, que es la queja concreta del relevamiento.

### Qué falta

1. **Definición del sorteo guardada en el examen**, no su resultado: categoría (con
   subcategorías sí o no), cantidad, y opcionalmente etiqueta. Puede haber varios
   tramos, por ejemplo 5 de una categoría y 5 de otra.
2. **Resolver el set por intento**, al arrancar cada alumno, y persistirlo en el intento
   para que la corrección y la revisión reconstruyan exactamente lo que rindió.
3. **Vista previa de la pregunta** desde el banco y desde el armado del examen, tal como
   la ve el alumno. Esto es lo que se pidió como "desglose del detalle de la pregunta".
4. **Que el armado muestre qué se está seleccionando**: desglose por categoría, cuántas
   hay disponibles, cuántas se van a sortear y cuáles quedaron elegidas si el sorteo es
   fijo.
5. **Mezclar tramos fijos y aleatorios** en un mismo examen, como Moodle.

### Impacto

Toca la corrección, la revisión y el cálculo de nota, que hoy asumen un set único por
examen. Ojo con el bug ya conocido de `blank` duplicado en `grade_calculator`,
`revision_query` y `taking_service`: son tres lugares que hay que tocar coordinados.

**Terminada cuando**: dos alumnos del mismo examen reciben preguntas distintas, cada uno
se corrige contra las suyas, la revisión muestra las que le tocaron a cada uno, el banco
tiene vista previa, y el armado muestra el desglose de lo que se está eligiendo.

---

## T-12 · El tope de preguntas no se valida contra las seleccionadas

**Gobernanza**: BAJA

Bug concreto del relevamiento: se importan 20 preguntas, se seleccionan 10, y en "máximo
de preguntas" se puede escribir 20 sin que nada objete. El examen queda con un tope
imposible de alcanzar.

La única validación actual es que sea entero mayor a 0
(`frontend/src/screens/exam-detail/ConfiguracionExamenSection.tsx:85-87`). No se cruza
nunca contra la cantidad de preguntas realmente seleccionadas.

**Falta**: validar el tope contra las seleccionadas, en el backend y no solo en la UI, y
que el mensaje diga el número concreto: "el máximo no puede superar las 10 preguntas
seleccionadas".

**Ojo**: cuando exista T-10, "cantidad seleccionada" pasa a ser "cantidad que define el
sorteo", así que conviene resolver esta validación pensando en los dos casos o hacerla
directamente después de T-10 para no escribirla dos veces.

**Terminada cuando**: no se puede guardar un tope mayor a las preguntas disponibles, con
test del rechazo en el backend.

---

## T-13 · Configurar si el alumno ve los eventos de proctoring mientras rinde

**Gobernanza**: MEDIA

**Definido por el dueño (22/8)**: por defecto **no**. Hoy el alumno ve todos los eventos
que genera el proctoring mientras rinde, y no debería.

- Panel del alumno: `frontend/src/screens/examen/IntegridadPanel.tsx`
- Config por examen: `backend/app/domain/exam_content/config.py`

**Falta**: un campo de configuración por examen, con default en no mostrar, y que el
panel lo respete.

**Ojo**: esto es una decisión de producto con una contra real. Mostrar los eventos tiene
un efecto disuasivo y también le avisa al alumno que algo se está detectando, lo que baja
el reclamo posterior de "no sabía". Ocultarlos por defecto está bien pedido, pero conviene
que el alumno igual sepa **que** se está supervisando, aunque no vea el detalle evento
por evento. Eso ya lo cubre el consentimiento.

**Terminada cuando**: el examen tiene la opción, arranca en no, y el panel del alumno la
respeta.

---

## T-14 · Materias y comisiones: colapsar, paginar y ordenar

**Gobernanza**: BAJA

Problema concreto: con 40 alumnos inscriptos la pantalla queda ilegible. Todo aparece
expandido, no hay paginación, y no hay forma de organizar la vista.

- Pantalla: `frontend/src/screens/MateriasComisiones.tsx` y
  `frontend/src/screens/admin/components/ComisionesAccordionBody.tsx`

**Falta**:

1. Poder desplegar y colapsar cada comisión, en vez de tener todo abierto.
2. Paginación del listado de inscriptos.
3. Evaluar una **página propia por comisión** en vez de meter todo en el acordeón. Es
   probablemente lo correcto: ahí entran los inscriptos paginados, el export de T-03 y la
   asignación de tutores de T-04, que hoy compiten por el mismo espacio.

**Se cruza con T-03**: si se hace la página propia, el export vive ahí. Conviene decidir
las dos juntas y no hacer T-03 dos veces.

**Terminada cuando**: una comisión con 40 inscriptos se navega cómoda, con paginación y
sin scroll infinito.

---

## T-15 · Exportar notas y marcar el estado a mano

**Gobernanza**: MEDIA

**Caso real**: no en todos los campus hay API de Moodle disponible. Sin API, la nota se
devuelve exportándola y cargándola a mano en el campus. Hoy el estado de la nota depende
de la sincronización con Moodle, así que en ese escenario queda para siempre en pendiente
aunque la nota ya se haya cargado.

**Falta**:

1. Export de las notas del examen, con los alumnos que rindieron y su nota.
2. Poder **marcar el estado a mano**: quién ya tiene la nota cargada en el campus, sin
   pasar por el write-back automático.
3. Que el estado manual se distinga del automático en la UI y en la auditoría. No es lo
   mismo "el sistema confirmó que Moodle la recibió" que "una persona dice que la cargó".

**Ojo**: el estado manual es una afirmación humana, no una prueba. Tiene que quedar
registrado quién lo marcó y cuándo, y no debe poder pisar un estado confirmado por
sincronización real.

**Terminada cuando**: se exportan las notas, se puede marcar el estado a mano, y la
pantalla distingue claramente el origen de cada estado.

---

## T-16 · BUG: tras el alta por LTI la sesión muestra `lti:1:...` como usuario

**Gobernanza**: ALTA (auth)

**Síntoma**: el alumno entra por primera vez desde el campus, elige su usuario y
contraseña, y acto seguido la aplicación lo muestra como `lti:1:7` en vez del usuario que
acaba de elegir.

**Causa, confirmada leyendo el código**: el flujo son dos pasos
(`frontend/src/screens/LtiConfirmar.tsx:96` y `:115`):

1. `POST /lti/confirmar-provisioning` crea la cuenta con `username = lti:{deployment}:{sub}`
   y **emite el JWT de sesión ahí mismo**, con `preferred_username = "lti:1:7"`.
2. `PUT /auth/change-password` con `nuevo_username` renombra al usuario en la base
   (`auth/router.py:548`), pero devuelve **solo `{ok: true}`**
   (`CambiarContrasenaResponse`, `auth/router.py:463`). No re-emite el token.

Resultado: la base queda bien, el token queda viejo. El frontend lee el `preferred_username`
del JWT, así que muestra el nombre viejo hasta que la persona vuelve a loguearse.

**Arreglo**: que `change-password` re-emita el access token cuando cambió el `username`, y
que el frontend adopte el token nuevo. Alternativa más barata: forzar un refresh después
del paso 2.

**Terminada cuando**: al terminar el alta la aplicación muestra el usuario elegido, sin
volver a loguearse, con test del claim del token re-emitido.

---

## T-17 · BUG: materias y comisiones vacía, y encima miente

**Gobernanza**: MEDIA

**Causa confirmada el 22/8 reproduciéndolo en producción**: es el MISMO bug del token
vencido que se arregló en `examContentAdmin` (ver commit `df4b688`). `examContentCatalog.ts`
es uno de los 12 módulos que todavía arman el `Bearer` a mano y no refrescan.

Traza real con el token vencido: `GET /exam-content/materias` → **401**, sin ningún intento
de refresh.

**Y hay un segundo defecto, más grave que el primero**: ante el 401 la pantalla no muestra
un error. Muestra:

> "No hay materias registradas. Creá la primera usando el botón de arriba."

O sea, le dice al usuario que sus datos NO EXISTEN cuando en realidad el request falló.
Alguien puede creer que perdió las materias y ponerse a crearlas de nuevo, duplicando todo.
Un fallo de carga nunca debe renderizarse como estado vacío.

**Arreglo, en dos partes**:

1. Usar `fetchAutenticado` en `examContentCatalog.ts` (reemplazo mecánico, ya existe el
   helper en `frontend/src/lib/fetchAutenticado.ts`).
2. Separar "cargó y no hay nada" de "no pudo cargar" en la pantalla, con estado de error y
   botón de reintentar. Revisar el resto de las pantallas por el mismo patrón.

**Terminada cuando**: con el token vencido la pantalla se recupera sola, y si el backend
falla de verdad muestra un error con reintentar, nunca el mensaje de vacío.

---

## T-18 · BUG: errores de mapeo en Auditoría (null y hashes sin normalizar)

**Gobernanza**: MEDIA

**Síntoma**: en Auditoría muchos campos se ven como `null` o como hashes crudos. Nada está
normalizado para que lo lea una persona.

- Pantalla: `frontend/src/screens/Auditoria.tsx`

Ya hay un mapa de acciones a etiquetas legibles (`rutaDeModulo`, `rutaDeAccion`, la tabla
de labels), pero está incompleto: lo que no matchea cae crudo a la pantalla.

**Falta**: revisar el mapeo entero contra las acciones que el backend emite de verdad
(`backend/app/application/audit/acciones.py`), completar las que faltan, y definir un
fallback legible para lo desconocido en vez de mostrar `null`. Los hashes de la cadena de
custodia deberían mostrarse acortados y con su significado, no como un blob.

**Ojo**: la auditoría es registro inalterable con cadena de hash. Se puede cambiar cómo se
**muestra**, nunca lo que se guarda.

**Terminada cuando**: no aparece ningún `null` en pantalla, cada acción tiene etiqueta en
castellano y los hashes se muestran acortados y explicados.

---

## T-19 · El registro del LTI es manual y se pierde al recrear la base

**Gobernanza**: CRITICA (auth)

**Pasó de verdad el 22/8/2026**: nadie podía entrar desde el campus. Todo launch moría en
`POST /api/v1/lti/login` con `403 {"detail":"lti_iss_no_confiable"}`, **antes** de mirar
qué usuario era. No era un problema de permisos de una persona: estaba roto para todos.

**Causa**: la tabla `lti_deployment_confiable` es la raíz de confianza del flujo LTI y
**no tiene seed ni migración que la pueble**. Se carga a mano con
`POST /api/v1/admin/lti/deployments`. Cada vez que se recrea la base del backend, la fila
desaparece y el ingreso desde el campus se cae en silencio, sin que nada avise.

Se resolvió cargando la fila de nuevo, pero va a volver a pasar.

**Valores reales del campus test** (leídos del POST que manda Moodle):

| campo | valor |
|---|---|
| `iss` | `https://campustest.frm.utn.edu.ar` |
| `deployment_id` | `1` |
| `client_id` | `6w1huGZSwii82yL` |
| `jwks_uri` | `https://campustest.frm.utn.edu.ar/mod/lti/certs.php` |

### Por qué se carga a mano, y por qué eso no debería ser así

Hay que separar dos cosas que se confunden:

- **Que la habilitación sea explícita está bien.** Cada fila es un Moodle autorizado a
  crear cuentas en el sistema. Si se auto-creara con solo apuntar un Moodle a nuestra URL,
  cualquiera podría dar de alta alumnos. El diseño falla cerrado a propósito (design D2).
- **Que se cargue a mano, siempre, y con los IDs copiados de un request, está mal.** Eso
  no es seguridad, es una tarea manual frágil que nadie recuerda hasta que se rompe.

**Y hay un hueco concreto**: LTI 1.3 define el **registro dinámico** justamente para esto,
y nosotros lo tenemos **implementado a medias**. Existe
`GET /api/v1/lti/dynamic-registration` (`presentation/api/v1/lti/router.py:143`), que
publica la configuración de la herramienta para que Moodle la consuma. Pero **no hay
endpoint que RECIBA y persista el registro**: el `client_id` y el `deployment_id` que
Moodle genera nunca vuelven a nuestra base. Por eso terminan copiándose a mano.

### Falta, en orden de importancia

1. **Completar el registro dinámico.** Que registrar la herramienta desde Moodle cree la
   fila sola, con el `client_id` y el `deployment_id` reales, sin que nadie copie nada.
   **Con una salvedad de seguridad**: la fila se crea `activo=false`, y un admin la
   habilita desde una pantalla. Sigue habiendo aprobación humana explícita, pero es un
   click en vez de un POST armado a mano. Así se conserva la propiedad de seguridad y
   desaparece la tarea manual.
2. **Que el sistema avise.** Un chequeo de salud que grite si la allowlist está vacía. Hoy
   la única señal es que los alumnos no pueden entrar, y eso se descubre tarde y de la
   peor forma.
3. **Pantalla de administración** para ver, habilitar y deshabilitar deployments. Hoy solo
   existe la API (`admin/lti_router.py`): sin UI, todo depende de que alguien sepa hacer el
   POST.
4. **Que sobreviva a recrear la base**: si el registro dinámico queda hecho, esto se
   resuelve solo volviendo a registrar desde Moodle. Mientras tanto, un seed explícito y
   auditable, nunca un "crear si no existe" con valores adivinados.

**Pendiente relacionado**: la fila quedó cargada **sin `comision_id`**, así que el alumno
que entra por el campus se crea pero no se matricula solo en ninguna comisión. Hay que
decidir a qué comisión mapear el curso de Moodle.

**Terminada cuando**: recrear la base no rompe el ingreso por campus, y si igual quedara
vacía el sistema avisa antes de que lo descubra un alumno.

---

## T-20 · Producción corre en un solo core

**Gobernanza**: ALTA (toca el arranque de producción)

El commit `0bb7c37` del 21/8 arregló cuatro cosas encontradas probando con carga real
de 150 a 1200 alumnos concurrentes. Tres llegaron a producción: pool de DB dimensionado
(`pool_size=12, max_overflow=12`), métricas Prometheus en `/metrics` (verificado, responde
200 en producción) y el logging de errores de DB que antes se tragaban.

**La cuarta no llegó.** El propio commit lo aclara: "No se tocó Dockerfile.activeexam".

| dónde | comando |
|---|---|
| `Dockerfile.activeexam:76` (producción) | `uvicorn ... --proxy-headers` **sin `--workers`** |
| `docker-compose.dev.yml` (desarrollo) | `uvicorn ... --workers 4` |

Producción levanta un solo proceso, así que usa un solo core por más cores que tenga el
host. Y el pool de 24 conexiones se dimensionó pensando en varios workers. Para 500
personas en vivo, este es hoy el cuello más probable.

### Actualización 22/8: el plan es free, así que los workers están descartados

Medido sobre la instancia de producción ese día: **186 MB de memoria en reposo**, sobre
los 512 MB del plan free de Render. Un segundo proceso son otros ~186 MB, y bajo carga
sube. `--workers 4` no entra en memoria: la instancia muere antes de atender a nadie.

O sea que esta task **no es "poner workers"**. En el plan actual no hay nada que tunear:
el techo es el plan. Poner workers solo tiene sentido después de mover a un plan con
memoria y cores para sostenerlos.

**Cuidado al hacerlo**, cuando se haga: `workers × (pool_size + max_overflow)` no puede
superar el `max_connections` de Postgres. Con 24 por worker, 4 workers son 96 conexiones.

### Lo que NO se sabe, y hay que medir antes de decidir nada

**Cuántos alumnos concurrentes aguanta `main_activeexam` en el plan free.** Nunca se
midió. Los números que circulan son de otra cosa:

- La corrida de 150 a 1200 del 21/8 fue **local**, en la máquina del dueño, con
  `--workers 4` y todos sus cores (`prometheus.dev.yml` apunta a `backend:8000`, el
  servicio del compose dev). No tocó Render.
- El límite de 25 a 30 alumnos de `results-4core-baseline.md` es de la **PoC C-03**, que
  es otra arquitectura (WebSocket, paneles SSE, LISTEN/NOTIFY). `main_activeexam` es REST
  simple y bastante más barato por request. **Ese número no se traslada.**

Que funcione hoy con unas pocas personas probando a mano no dice nada sobre 500.

**Otros dos límites del free que pegan el día del examen**:

- **Spin down** tras 15 minutos sin tráfico. Observado el 22/8: el primer login tardó
  tanto que parecía roto. El primer alumno en llegar se come el arranque completo.
- **La base free se vence y se recrea.** Es la explicación más probable de por qué
  desapareció la fila de confianza LTI (ver T-19): los 7 usuarios de la base están todos
  creados el 19/8 y no hay ni un usuario LTI. Si es eso, **va a volver a pasar solo**.

**Terminada cuando**: hay una medición del sistema real (T-22) y, con ese número, un plan
dimensionado para la concurrencia del examen. Antes de eso no hay nada que configurar.

---

## T-21 · Nadie mira las métricas en producción

**Gobernanza**: MEDIA

`/metrics` responde 200 en producción, pero **no hay nada que lo scrapee**. Prometheus
solo existe en el compose local. En Render no corre.

O sea que hoy las métricas existen y se pierden: no hay serie histórica. Si algo se cae
durante el examen real, no vas a poder reconstruir qué pasó.

**Falta**: un Prometheus (o un servicio gestionado) que scrapee el `/metrics` de
producción y guarde la serie, con retención que cubra el examen y los días posteriores.

**Ojo**: `/metrics` hoy es **público**. Antes de exponerlo a internet para que algo
externo lo scrapee, conviene protegerlo: no filtra datos personales, pero sí la forma de
la API y el volumen de uso.

**Terminada cuando**: hay serie histórica consultable de la ventana del examen real.

---

## T-22 · Repetir la medición de carga y dejarla escrita

**Gobernanza**: BAJA

De la corrida de 150 a 1200 del 21/8 **no quedó ningún documento**: ni cuánto aguantó, ni
dónde estuvo el quiebre, ni con qué hardware. Y no se podía repetir, porque el único k6
del repo (`poc/k6/students.js`) le pega al backend del PoC C-03, que es otra arquitectura.

**Hecho el 22/8** (ya no falta):

- `tools/carga/carga-activeexam.js`: k6 contra el backend real, simulando el camino
  caliente (crear sesión, stream de eventos, finalizar) con umbrales p95 < 500 ms,
  p99 < 1 s y menos de 1 % de error.
- `tools/carga/README.md` con cómo correrlo.
- Prometheus y Grafana **dentro** del compose de desarrollo, con volumen y con el
  dashboard versionado en `infra/observability/grafana/dashboards/activeexam-carga.json`.
  Antes se levantaban a mano por fuera de todo compose y los paneles morían con el
  contenedor.

**Falta**: correr la medición y escribir los resultados. Idealmente dos corridas, antes y
después de T-20, para tener el número con y sin workers.

**Terminada cuando**: hay un documento con el punto de quiebre medido, el hardware y la
configuración, igual que `results-4core-baseline.md` pero del sistema real.

---

## Orden sugerido

**Definido por el dueño (22/8)**: las preguntas aleatorias (T-10) van **al final**.
Primero todo lo demás.

0. **T-20 y T-22 antes que nada, si el examen real se acerca.** Que el sistema no aguante
   la concurrencia el día de la rendición es peor que cualquier bug de esta lista: no hay
   workaround en el momento. T-22 ya tiene el harness listo, solo falta correrlo, y su
   resultado es el que dice si T-20 es urgente o no.
1. **T-19**: es lo único de la lista que deja el sistema inutilizable para TODOS los
   alumnos, sin aviso. Que vuelva a pasar el día del examen es el otro escenario malo.
2. **Resto de bugs**: T-17 (causa ya confirmada, arreglo conocido), T-16 (usuario LTI) y
   T-18 (auditoría).
3. **T-04**: ya está escrito, solo falta cerrarlo y desplegarlo.
4. **T-07** (rol PROFESOR) antes que T-02, T-08 y T-09: los tres dependen del mapa de
   roles, y hacerlos antes obliga a rehacerlos.
5. **T-02, T-08, T-09** juntos: son el mismo trabajo de acotar por rol, en tres pantallas.
   Un solo change de autorización, no tres parches.
6. **T-01, T-13**: las dos son configuración por examen con default nuevo. Entran juntas
   y son baratas.
7. **T-14 y T-03** juntas: si se hace la página propia por comisión, el export vive ahí.
8. **T-05, T-06, T-15**: independientes, entran cuando haya lugar.
9. **T-10** al final, con su propio change, y **T-12** pegada atrás para no escribir la
   validación dos veces.

## Preguntas abiertas

Ninguna bloquea. Todas quedaron definidas por el dueño el 22/8/2026 y están escritas en
cada task: T-01 (default `nunca` más botón de publicar), T-05 (replicado por comisión),
T-07 (el profesor no emite veredicto, el coordinador conserva todo), T-10 y T-11
(unificadas en el modelo de sorteo de Moodle), T-13 (eventos ocultos por defecto).

Lo único a decidir al implementar es si T-14 se resuelve con acordeón o con página propia
por comisión, porque de eso depende dónde vive el export de T-03.
