# Proposal — C-79 `permisos-nm-coordinador`

> **Nota de procedencia (22/8/2026)**: este change se escribió **después** de que el
> código ya estuviera implementado. El trabajo se hizo bajo la etiqueta "c-79" sin que
> existiera el change, en violación de la regla dura #2 del proyecto ("no se codea fuera
> de un change"). Se documenta acá para que el plan y el código digan lo mismo, y se
> archiva en el mismo acto porque las tasks ya están cumplidas. **No es un permiso para
> repetir el atajo**: el costo de reconstruir el proposal a posteriori, leyendo diffs,
> es mayor que el de escribirlo antes.
>
> Commit del código: `28b1ee8`.

## Why

Dos problemas distintos que el mismo trabajo tuvo que tocar a la vez.

**1. Los permisos eran 1:1 donde la realidad es N:M.** Una comisión tenía UN docente
(`comision.docente_id`), pero en la práctica una comisión puede tener varios tutores, y
una materia varios coordinadores. Modelarlo 1:1 obligaba a elegir a uno y dejar al resto
sin acceso a lo suyo.

**2. El COORDINADOR veía todo el sistema.** No tenía acotamiento por pertenencia: podía
leer sesiones, exámenes y notas de materias que no coordinaba. En un sistema donde el
veredicto de integridad es suyo, ese alcance de más es un problema de gobierno, no de
comodidad.

Sumado a eso, `ver_estadisticas` incluía a TUTOR. Son agregados sin datos personales,
pero exponen el rendimiento de **cualquier** materia, comisión o examen vía query params,
sin scoping por pertenencia: un tutor podía pedir el resumen de una comisión ajena.

**3. Auditoría no podía resolver a quién ni a qué se refería una entrada.** Filas con
`entidad_id` pero sin `entidad` quedaban sin tipo, así que la pantalla no podía armar el
"Ver detalle" aunque tuviera el id. Y el actor de los pedidos DSR se guardaba como
`"{uuid}:dsr"`, que Auditoría no podía traducir a un nombre visible.

## What Changes

### Permisos N:M

- Tablas `comision_tutor` y `materia_coordinador` (migración `0086`). Una comisión puede
  tener varios tutores; una materia, varios coordinadores.
- El COORDINADOR pasa a estar acotado por pertenencia: **sin materias asignadas no ve
  nada**. `admin_sistema` queda como el único rol con alcance global.
- `ver_estadisticas` sale de TUTOR. Queda en COORDINADOR y ADMIN_SISTEMA.
- La lectura del panel académico, el catálogo, el registro de sesiones y las estadísticas
  se acotan por las nuevas tablas de pertenencia.

### Auditoría

- `entidad_de_accion`: fallback que deriva el tipo de entidad a partir de la acción,
  mismo mecanismo que `modulo_de_accion` (C-76). Cierra la clase de bug de la fila sin
  tipo.
- El actor de los pedidos DSR pasa a ser el email o username real de quien ejecuta.
- `verify_chain` resuelve la sesión dueña del evento, para linkear al detalle de
  proctoring en vez de caer al listado genérico.

## Non-Goals

- **No** se dropea `comision.docente_id`. Queda como columna muerta hasta confirmar que
  ningún lector la usa. Es deuda abierta, anotada como T-04 del relevamiento.
- **No** se agregan roles nuevos. El rol PROFESOR es otro trabajo (T-07).
- **No** se rediseña la pantalla de Auditoría. Sigue habiendo campos que se muestran como
  `null` o como hash crudo: eso lo cubre c-78 (`filtro-etiqueta-fiel`) y T-18.
