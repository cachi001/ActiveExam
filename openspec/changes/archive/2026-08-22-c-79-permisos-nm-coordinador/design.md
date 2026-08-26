# Design — C-79 `permisos-nm-coordinador`

Reconstruido a partir del código implementado (commit `28b1ee8`).

## D1 — Tablas de unión en vez de arrays o JSON

`comision_tutor` y `materia_coordinador` son tablas de unión con UNIQUE sobre el par y
FKs con `ondelete`. Se descartó guardar los ids en un array o en JSON sobre la fila
padre: la pertenencia se consulta en cada request de autorización, y una tabla indexada
resuelve eso con un JOIN en vez de un escaneo.

## D2 — `docente_id` se conserva muerto

La migración `0086` copia los `docente_id` existentes a `comision_tutor` pero **no dropea
la columna**. Dropear una columna que todavía puede tener lectores es una migración
destructiva; el proyecto exige hacerlas en dos pasos. Primer paso: dejar de escribirla y
de leerla. Segundo paso, en otro change: dropearla.

## D3 — El coordinador falla cerrado

Un coordinador **sin** materias asignadas no ve nada, en vez de ver todo. Es la decisión
opuesta a la anterior y es deliberada: el alcance se gana por asignación explícita. El
costo es que al crear un coordinador nuevo hay que acordarse de asignarle materias, o va
a reportar que "no anda". Se aceptó ese costo a cambio de que no haya alcance implícito.

## D4 — `ver_estadisticas` sin TUTOR

Los agregados no tienen datos personales, así que la tentación es dejarlos abiertos. Se
cerró igual porque los endpoints aceptan query params de materia, comisión y examen **sin
scoping por pertenencia**: el agregado es inocuo, pero el filtro arbitrario convierte el
endpoint en una ventana a cualquier comisión. Acotar el endpoint por pertenencia hubiera
sido la alternativa; se eligió sacar la capacidad porque el tutor no tiene un caso de uso
para estadísticas institucionales.

## D5 — Fallback de entidad, no validación estricta

Ante una fila de auditoría con `entidad_id` pero sin `entidad`, había dos caminos:
rechazar la escritura (obligando a todos los callers a pasar ambos), o derivar la entidad
de la acción. Se eligió derivar, por el mismo criterio que `modulo_de_accion` en C-76: el
audit log **nunca** debe rechazar una escritura por un dato de presentación faltante. Que
una acción quede sin registrar es peor que una que se registra con el tipo derivado.

## Riesgo asumido

Los dos cuerpos de trabajo (permisos y auditoría) se implementaron entrelazados y se
commitearon juntos. Separarlos a posteriori hubiera requerido partir hunks a mano, con
riesgo de perder trabajo. Se documentó la mezcla en el mensaje del commit.
