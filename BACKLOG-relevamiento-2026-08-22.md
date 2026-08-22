# Relevamiento del 22/8/2026 — tasks pendientes

Pedido del dueño del proyecto tras probar el sistema. Cada task lleva: qué se pide,
dónde vive hoy en el código, qué falta y con qué se da por terminada. El nivel de
gobernanza indica cuánta autonomía tiene el agente que la implemente (CRITICO y ALTO
requieren aprobación humana antes de escribir código).

Orden sugerido de ataque al final del documento.

---

## T-01 · "Nunca" como opción por defecto de mostrar la nota

**Gobernanza**: MEDIA

Hoy `mostrar_nota` acepta solo dos valores y arranca en `al_cerrar`:

- `backend/app/presentation/api/v1/exam_content/schemas.py:713` → default `"al_cerrar"`
- `backend/app/presentation/api/v1/exam_content/schemas.py:749` → `Literal["al_cerrar", "inmediata"]`
- UI: `frontend/src/screens/exam-detail/ConfiguracionExamenSection.tsx:53`

**Falta**: un tercer valor `nunca`, que además pase a ser el default y el recomendado
en la UI (el alumno no ve la nota en la plataforma; la nota vive en Moodle).

**Ojo con la regla de monotonía**: `backend/app/domain/exam_content/config.py:101-104`
restringe cómo puede cambiar `mostrar_nota` una vez que el examen tiene intentos
(hoy: de `inmediata` no se puede retroceder). Hay que decidir dónde entra `nunca` en
ese orden antes de tocar el enum, porque afecta a exámenes ya rendidos.

**Terminada cuando**: el enum tiene los tres valores, un examen nuevo arranca en
`nunca`, la UI lo marca como recomendado, la migración define qué pasa con los
exámenes existentes y hay test de la transición de estados permitida.

---

## T-02 · El dashboard muestra según el rol

**Gobernanza**: ALTA (toca autorización)

Hoy el tutor ve el menú completo. No debería tener acceso a Estadísticas, Creación de
exámenes ni Banco de preguntas: solo lo suyo.

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

**Falta**: pasar la relación a N:M (tabla `examen_comision`) o permitir crear el examen
replicado por comisión. Hay que decidir cuál de las dos, porque cambia todo lo que
cuelga del examen: resultados, destino de la nota en Moodle (que es por examen), y el
gate de quién puede rendirlo.

**Ojo**: el destino de la nota (`moodle_courseid` + `moodle_cmid`) es por examen. Si un
examen abarca varias comisiones de cursos distintos de Moodle, el destino tiene que
pasar a ser por comisión o el write-back manda todo al mismo lugar.

**Terminada cuando**: se crea un examen eligiendo varias comisiones, cada alumno lo ve
desde la suya, y la nota vuelve al curso correcto de cada una.

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

**A resolver antes de codear**: en qué se diferencia de COORDINADOR, que hoy ya supervisa
y emite veredicto. Si PROFESOR también supervisa en vivo, hay que definir si emite
veredicto o no, porque la separación entre quien pone la nota y quien juzga la integridad
es una decisión de diseño explícita del proyecto (ver el comentario de `TUTOR` en
`roles.py`).

**Terminada cuando**: existe el rol, tiene sus capacidades en `capabilities.py`, hay
migración, y hay test por endpoint de lo que puede y de lo que no.

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

## T-10 · Sorteo aleatorio por alumno, como Moodle

**Gobernanza**: MEDIA

Hoy existe `POST /exam-content/{examen_id}/sortear-preguntas`
(`catalog_router.py:2529`, `repo.sortear_por_categorias`), pero sortea UN set fijo para
el examen: todos los alumnos reciben las mismas preguntas.

**Falta**: el modelo de Moodle, donde el examen define "10 preguntas al azar de esta
categoría o subcategoría" y CADA alumno recibe su propia selección al empezar.

Implica guardar la definición del sorteo en el examen (categoría + cantidad) y resolver
el set concreto por intento, no por examen. Impacta en la corrección, en la revisión y
en el cálculo de nota, que hoy asumen un set único.

**Terminada cuando**: dos alumnos del mismo examen reciben preguntas distintas, cada uno
se corrige contra las suyas, y la revisión muestra las que le tocaron a cada uno.

---

## T-11 · Desglose del detalle de la pregunta

**Gobernanza**: BAJA

**Falta**: definir con precisión qué se quiere ver. Interpretación probable: por pregunta,
cuántos la respondieron bien y mal, distribución de las opciones elegidas y dificultad
resultante, para detectar preguntas mal formuladas.

**Pendiente**: confirmar con el dueño si es esto o si se refiere a ver el detalle de la
pregunta dentro del intento de un alumno.

**Terminada cuando**: la definición está confirmada y la pantalla la muestra.

---

## Orden sugerido

1. **T-04** primero: ya está escrito, solo falta cerrarlo y desplegarlo.
2. **T-07** (rol PROFESOR) antes que T-02, T-08 y T-09: los tres dependen de cómo quede
   el mapa de roles, y hacerlos antes obliga a rehacerlos.
3. **T-02, T-08, T-09** juntos: son el mismo trabajo de acotar por rol, en tres pantallas.
   Conviene un solo change de autorización y no tres parches.
4. **T-01, T-03, T-06**: independientes y chicos, entran en cualquier momento.
5. **T-05** y **T-10**: los más invasivos, tocan el modelo de datos del examen y arrastran
   corrección, revisión y write-back. Van al final y con su propio change cada uno.

## Preguntas abiertas que bloquean

- T-01: ¿dónde entra `nunca` en la regla de monotonía de exámenes ya rendidos?
- T-05: ¿examen N:M contra comisiones, o un examen replicado por comisión? ¿El destino de
  la nota pasa a ser por comisión?
- T-07: ¿PROFESOR emite veredicto de integridad o solo supervisa?
- T-11: ¿desglose estadístico por pregunta, o detalle de la pregunta dentro del intento?
