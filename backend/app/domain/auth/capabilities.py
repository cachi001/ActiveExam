"""Capa de capacidades config-driven (capacidad -> roles), c-71 slice 2 D8.

Reemplaza el `require_roles` hardcodeado por endpoint para la accion de la
Cola de Revision:

- ``revisar_sesion``: decision TERMINAL de la sesion, en un solo acto —
  aprobar o anular. NO hay una capacidad separada para "resolver" un caso
  abierto: el owner del proyecto rechazo explicitamente el modelo de dos
  fases ("no existe el caso abierto, nunca dije que era un estado y no lo
  va a ser"; confirmado: "si, un solo paso: quien revisa decide", sin
  segunda instancia). Quien tiene `revisar_sesion` puede aprobar Y anular.

Sin framework ni infraestructura (D1): dominio puro, testeable sin DB/red.
"""

from __future__ import annotations

from app.domain.auth.roles import Rol

# capacidad -> conjunto de roles que la poseen. Dato de config, no logica.
CAPABILITY_ROLES: dict[str, frozenset[Rol]] = {
    # --- Circuito de revision humana (L2.5) ---------------------------------
    # c-76: el rol REVISOR fue eliminado; el COORDINADOR (ya presente) absorbe el
    # veredicto que tenia el revisor. Sin duplicado — el set no cambia de tamano.
    # c-78 D11: PROFESOR queda DELIBERADAMENTE afuera. Es lo que lo distingue del
    # COORDINADOR: mira la evidencia y el score, pero no emite el veredicto.
    # Quien pone la nota no decide si hubo fraude (regla dura #5).
    "revisar_sesion": frozenset({Rol.COORDINADOR, Rol.ADMIN_SISTEMA}),
    # --- Gestion academica ---------------------------------------------------
    # Alta/edicion de examenes, materias y comisiones. El DOCENTE vive aca: es su
    # trabajo. Quien juzga el fraude no edita el examen.
    # LECTURA del catalogo academico (que materias/comisiones/examenes existen y
    # cuales son "los mios"). Toda ESCRITURA cuelga de una capacidad mas acotada:
    # `gestionar_estructura` (materias/comisiones/padron), `crear_examenes` o
    # `gestionar_banco`. El tutor tiene esta y solo esta del lado academico.
    "gestionar_academico": frozenset(
        {Rol.TUTOR, Rol.PROFESOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
    # c-78 (E-04/E-03, D11): CREAR y editar examenes. Se separo de
    # `gestionar_academico` porque el TUTOR conserva esa (leer su catalogo,
    # inscribir, cerrar notas) pero PIERDE la creacion: armar el examen es
    # trabajo del PROFESOR, no de quien lo dicta y acompana. Sin este split,
    # sacarle la creacion al tutor le sacaba tambien las notas y las
    # inscripciones, que si son suyas.
    "crear_examenes": frozenset(
        {Rol.PROFESOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
    # c-78 (E-03): el BANCO de preguntas (categorias, preguntas, import XML).
    # Mismo criterio que `crear_examenes`, y por la misma razon esta separado:
    # el banco es el contenido con las respuestas correctas de toda la materia,
    # no el material de una comision.
    "gestionar_banco": frozenset(
        {Rol.PROFESOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
    # La ESTRUCTURA academica completa: materias, comisiones y el PADRON
    # (inscribir y desinscribir alumnos).
    #
    # Deliberadamente SIN TUTOR (decision del dueno, c-78): el tutor NO toca nada
    # de Materias y comisiones — ni crea, ni edita, ni inscribe, ni desinscribe.
    # Acompana su comision, cierra notas y supervisa; administrar el padron y la
    # grilla es de otro. El PROFESOR entra aca porque es quien arma la materia.
    #
    # OJO con el alcance: `gestionar_academico` (que el tutor SI tiene) es solo
    # LECTURA del catalogo. Toda escritura sobre materia/comision/inscripcion
    # cuelga de esta capacidad, endpoint por endpoint.
    "gestionar_estructura": frozenset(
        {Rol.PROFESOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
    # Ver las notas y sincronizarlas a Moodle: el docente necesita cerrar la nota
    # de su materia.
    "gestionar_notas": frozenset(
        {Rol.TUTOR, Rol.PROFESOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
    # Ver estadisticas institucionales agregadas (dashboard/exportables).
    # Deliberadamente SIN TUTOR: aunque son agregados sin PII, exponen el
    # rendimiento de CUALQUIER materia/comision/examen via query params sin
    # scoping por pertenencia (el docente podria pedir el resumen de una
    # comision ajena). Decision del owner: el tutor gestiona SU catalogo
    # (`gestionar_academico`/`gestionar_notas`) pero no mira estadisticas
    # institucionales — eso es coordinacion/administracion.
    # c-78: el PROFESOR entra aca (D11: conserva estadisticas). El TUTOR sigue
    # deliberadamente afuera, por la razon de arriba.
    "ver_estadisticas": frozenset(
        {Rol.PROFESOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
    # Asignar el docente a cargo de una comision (C-73 §9). Deliberadamente SIN
    # DOCENTE: quien queda a cargo decide quien devuelve la nota a Moodle y que
    # examenes puede tocar. Si el docente pudiera asignarse solo, la pertenencia
    # dejaria de ser un control (se auto-otorgaria el acceso que el control niega).
    "asignar_docente": frozenset(
        {Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
    # --- Administracion del sistema -----------------------------------------
    # Umbrales, detectores, retencion. Deliberadamente SIN docente: la
    # configuracion define como se detecta el fraude; quien dicta la materia no
    # debe poder aflojarla para su propio examen.
    "configurar_sistema": frozenset({Rol.ADMIN_SISTEMA}),
    # Alta/baja de usuarios y asignacion de roles: solo admin del sistema.
    "gestionar_usuarios": frozenset({Rol.ADMIN_SISTEMA}),
    # Registro inmutable: lo lee quien audita, no quien opera. c-76-2: el rol
    # AUDITOR fue eliminado (nunca tuvo un endpoint real conectado a esta
    # capacidad — audit_router.py ya usaba require_roles(ADMIN_SISTEMA)
    # hardcodeado); queda exclusiva de ADMIN_SISTEMA.
    "ver_auditoria": frozenset({Rol.ADMIN_SISTEMA}),
    # --- Supervision en vivo -------------------------------------------------
    # Mirar sesiones en curso. c-76: el rol PROCTOR fue eliminado y el TUTOR entra
    # aca (supervisa a sus alumnos en vivo, acotado por comision en la capa de
    # aplicacion — Tarea 8). El TUTOR mira, pero NO decide: el VEREDICTO
    # (`revisar_sesion`) sigue SIN TUTOR (coordinador/admin, tras eliminarse
    # tambien REVISOR — c-76), preservando la separacion "quien dicta la materia
    # no juzga el fraude".
    "supervisar_vivo": frozenset(
        {Rol.TUTOR, Rol.PROFESOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
}


def tiene_capacidad(rol: Rol, capacidad: str) -> bool:
    """``True`` si ``rol`` esta en el conjunto de roles de ``capacidad``.

    Una capacidad no declarada en el mapa deniega por defecto (fail-closed)."""
    return rol in CAPABILITY_ROLES.get(capacidad, frozenset())
