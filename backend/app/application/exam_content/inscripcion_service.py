"""Servicio de inscripción de alumnos a comisiones + elegibilidad (C-69).

Casos de uso (admin):
- ``inscribir``: inscribe un alumno a una comisión (valida que ambos existan).
- ``eliminar``: da de baja una inscripción.
- ``listar_alumnos_con_elegibilidad``: lista los inscriptos de una comisión,
  resolviendo por cada uno si "puede rendir" (consentimiento vigente + biometría
  vigente), reusando los repos de consentimiento de perfil y embedding de referencia.

L2.5: la elegibilidad PRIORIZA/gatea la rendición; no sanciona. La decisión la
toma el sistema sobre datos server-side (cliente = sensor no confiable).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.exam_content.errors import (
    CodigoMatriculacionInvalidoError,
    ComisionInactivaError,
    ComisionNoEncontradaError,
    InscripcionConActividadError,
    InscripcionNoEncontradaError,
    MateriaInactivaError,
    PerfilIncompletoError,
    UsuarioNoEncontradoError,
    YaInscriptoEnLaMateriaError,
)
from app.domain.exam_content.errors import InscripcionDuplicadaError


async def _rechazar_si_ya_esta_en_la_materia(
    inscripcion_repo, usuario_id: str, comision_id: str
) -> None:
    """UNA SOLA COMISIÓN POR MATERIA (c-78, decisión del dueño).

    Función de módulo, no método: la comparten los DOS servicios de inscripción
    (el del alumno con el código y el del admin). Si viviera en uno solo, el otro
    camino dejaría pasar la doble matrícula y la regla no existiría.

    Ver ``YaInscriptoEnLaMateriaError`` para el porqué.
    """
    previa = await inscripcion_repo.comision_previa_en_la_materia(usuario_id, comision_id)
    if previa is None:
        return
    raise YaInscriptoEnLaMateriaError(
        f"Ya estás inscripto a la comisión {previa.nombre!r} de esta materia. "
        "No se puede cursar la misma materia en dos comisiones: pedile al "
        "docente que te cambie.",
        comision_actual_nombre=previa.nombre,
    )


@dataclass(frozen=True)
class AlumnoElegibilidad:
    """Fila de elegibilidad de un alumno inscripto a una comisión.

    ``puede_rendir`` = consentimiento_vigente AND biometria_vigente. ``razon`` es
    None cuando puede rendir; cuando no, describe qué falta (consentimiento,
    biometría, o ambos).
    """

    usuario_id: str
    username: str
    nombre: str | None
    apellido: str | None
    email: str
    consentimiento_vigente: bool
    biometria_vigente: bool
    puede_rendir: bool
    razon: str | None
    # c-78 §13.4: cuándo se inscribió. Es la columna que permite cruzar el listado
    # contra el padrón del campus ("este se anotó después del cierre de
    # inscripción"). None solo si el dato no vino proyectado.
    inscripto_en: object | None = None


@dataclass(frozen=True)
class InscripcionPorCodigoResult:
    """Resultado de la auto-matriculación por código (C-70).

    ``ya_inscripto`` = True cuando el alumno ya estaba inscripto en esa comisión
    (idempotente, no error). Los ``*_nombre`` identifican a qué quedó matriculado.
    """

    comision_id: str
    comision_nombre: str
    materia_nombre: str
    ya_inscripto: bool


class AutoMatriculacionService:
    """Caso de uso ESTUDIANTE: auto-matriculación a una comisión por código (C-70, D4).

    Reutiliza los repos existentes sin duplicar lógica de elegibilidad: la
    matriculación es solo set-membership; el gate ``puede_rendir`` (consentimiento +
    biometría, server-side) NO se toca. El ``usuario_id`` lo provee el caller desde
    el principal autenticado — NUNCA del body (regla dura #6, cliente no confiable).
    """

    def __init__(
        self,
        comision_repo,
        materia_repo,
        inscripcion_repo,
        consent_repo,
        embedding_repo,
        foto_repo,
    ) -> None:
        self._comision_repo = comision_repo
        self._materia_repo = materia_repo
        self._inscripcion_repo = inscripcion_repo
        self._consent_repo = consent_repo
        self._embedding_repo = embedding_repo
        self._foto_repo = foto_repo

    async def _asegurar_perfil_completo(self, usuario_id: str) -> None:
        """Gate C-71 (+ foto obligatoria): el alumno DEBE tener el perfil completo
        para matricularse.

        Perfil completo = consentimiento vigente 'otorgado' + referencia biométrica
        vigente + **foto de perfil de referencia** (server-side; no se puede saltear
        desde el cliente — decisión del dueño: la foto es obligatoria). Eleva
        PerfilIncompletoError describiendo qué falta.
        """
        consentimiento = await self._consent_repo.vigente(usuario_id)
        consentimiento_ok = (
            consentimiento is not None and consentimiento.estado == "otorgado"
        )
        biometria_ok = await self._embedding_repo.obtener_vigente(usuario_id) is not None
        foto_ok = await self._foto_repo.obtener_vigente(usuario_id) is not None
        if not (consentimiento_ok and biometria_ok and foto_ok):
            raise PerfilIncompletoError(
                _razon_matricula(consentimiento_ok, biometria_ok, foto_ok)
            )

    async def inscribir_por_codigo(
        self, codigo_matriculacion: str, usuario_id: str
    ) -> InscripcionPorCodigoResult:
        """Matricula al alumno a la comisión cuyo código coincide (idempotente).

        Gate C-71: exige el perfil completo (consentimiento + biometría) ANTES de
        matricular — la matriculación no se permite sin perfil (server-side).

        Raises:
            PerfilIncompletoError: el alumno no tiene el perfil completo (→ 403).
            CodigoMatriculacionInvalidoError: el código es vacío/malformado o no
                mapea a ninguna comisión (→ 404/422 en el endpoint; sin inscripción).
        """
        codigo = (codigo_matriculacion or "").strip()
        if not codigo:
            raise CodigoMatriculacionInvalidoError("El código de matriculación es vacío.")

        # Gate de perfil PRIMERO: sin perfil no se matricula (regla del owner).
        await self._asegurar_perfil_completo(usuario_id)

        comision = await self._comision_repo.obtener_por_codigo_matriculacion(codigo)
        if comision is None:
            raise CodigoMatriculacionInvalidoError(
                f"El código {codigo!r} no corresponde a ninguna comisión."
            )

        # Freeze a nivel comisión (baja lógica, C-72 §17): una comisión desactivada
        # NO admite inscripciones nuevas, aunque su materia siga activa.
        if not comision.activa:
            raise ComisionInactivaError(
                f"La comisión {comision.nombre!r} está desactivada y no admite "
                "inscripciones nuevas."
            )

        materia = await self._materia_repo.obtener(comision.materia_id)
        materia_nombre = materia.nombre if materia is not None else ""

        # Freeze (C-72 §17): una materia desactivada NO admite inscripciones nuevas.
        # Los ya inscriptos conservan su acceso (esto solo bloquea altas nuevas).
        if materia is not None and not materia.activa:
            raise MateriaInactivaError(
                f"La materia {materia.nombre!r} está desactivada y no admite "
                "inscripciones nuevas."
            )

        # UNA SOLA COMISIÓN POR MATERIA (c-78, decisión del dueño). El código de
        # matriculación lo comparte el docente y no es secreto: sin esto, un
        # alumno conseguía el de otra comisión y quedaba en las dos, veía DOS
        # copias del mismo parcial y podía rendir las dos — y como las réplicas
        # comparten `moodle_cmid`, la segunda nota pisaba a la primera.
        await _rechazar_si_ya_esta_en_la_materia(
            self._inscripcion_repo, usuario_id, comision.id
        )

        # Idempotente: si ya está inscripto, el repo eleva InscripcionDuplicadaError
        # (rollback interno). No es error para el alumno: respuesta amistosa.
        try:
            await self._inscripcion_repo.inscribir(usuario_id, comision.id)
            ya_inscripto = False
        except InscripcionDuplicadaError:
            ya_inscripto = True

        return InscripcionPorCodigoResult(
            comision_id=comision.id,
            comision_nombre=comision.nombre,
            materia_nombre=materia_nombre,
            ya_inscripto=ya_inscripto,
        )


def _razon(consentimiento_vigente: bool, biometria_vigente: bool) -> str | None:
    """Texto de por qué un alumno NO puede rendir (None si puede)."""
    if consentimiento_vigente and biometria_vigente:
        return None
    if not consentimiento_vigente and not biometria_vigente:
        return "Falta consentimiento y biometría"
    if not consentimiento_vigente:
        return "Falta consentimiento"
    return "Falta biometría"


def _razon_matricula(
    consentimiento_vigente: bool, biometria_vigente: bool, foto_vigente: bool
) -> str:
    """Texto de qué falta para matricularse (consentimiento + biometría + foto).

    Se llama solo cuando falta al menos uno, así que nunca devuelve None.
    """
    faltantes: list[str] = []
    if not consentimiento_vigente:
        faltantes.append("consentimiento")
    if not biometria_vigente:
        faltantes.append("biometría")
    if not foto_vigente:
        faltantes.append("foto de perfil")
    if len(faltantes) == 1:
        return f"Falta {faltantes[0]}"
    return "Falta " + ", ".join(faltantes[:-1]) + " y " + faltantes[-1]


class InscripcionService:
    """Casos de uso (admin): inscribir/eliminar alumnos y listar con elegibilidad."""

    def __init__(
        self,
        inscripcion_repo,
        comision_repo,
        consent_repo,
        embedding_repo,
    ) -> None:
        self._inscripcion_repo = inscripcion_repo
        self._comision_repo = comision_repo
        self._consent_repo = consent_repo
        self._embedding_repo = embedding_repo

    async def inscribir(self, comision_id: str, usuario_id: str):
        """Inscribe un alumno a una comisión.

        Raises:
            ComisionNoEncontradaError: la comisión no existe.
            UsuarioNoEncontradoError: el usuario no existe (o está dado de baja).
            InscripcionDuplicadaError: el alumno ya está inscripto (lo eleva el repo).
        """
        comision = await self._comision_repo.obtener(comision_id)
        if comision is None:
            raise ComisionNoEncontradaError(f"Comisión {comision_id!r} no existe.")
        if not await self._inscripcion_repo.usuario_existe(usuario_id):
            raise UsuarioNoEncontradoError(f"Usuario {usuario_id!r} no existe.")
        # La misma regla que para el alumno: si el admin la puede violar, la
        # regla no existe. Para cambiar de comisión hay que dar de baja la
        # anterior primero, que además es la operación que tiene la guarda de
        # "ya rindió" (no se huerfaniza evidencia).
        await _rechazar_si_ya_esta_en_la_materia(
            self._inscripcion_repo, usuario_id, comision_id
        )
        return await self._inscripcion_repo.inscribir(usuario_id, comision_id)


    async def eliminar(self, comision_id: str, usuario_id: str) -> None:
        """Da de baja la inscripción del alumno a la comisión.

        Guarda (cadena de custodia): si el alumno YA rindió en la comisión, la baja
        se bloquea — borrarla huerfanaría la sesión/evidencia/nota.

        Raises:
            InscripcionConActividadError: el alumno tiene actividad (ya rindió).
            InscripcionNoEncontradaError: no existía la inscripción.
        """
        if await self._inscripcion_repo.alumno_rindio_en_comision(usuario_id, comision_id):
            raise InscripcionConActividadError(
                f"El alumno {usuario_id!r} ya rindió en la comisión {comision_id!r}: "
                "no se puede dar de baja la inscripción (se conserva la evidencia)."
            )
        eliminada = await self._inscripcion_repo.eliminar(usuario_id, comision_id)
        if not eliminada:
            raise InscripcionNoEncontradaError(
                f"No existe inscripción del usuario {usuario_id!r} a la comisión "
                f"{comision_id!r}."
            )

    async def listar_alumnos_con_elegibilidad(
        self, comision_id: str
    ) -> list[AlumnoElegibilidad]:
        """Lista los inscriptos de una comisión con su elegibilidad ("puede rendir").

        Por cada alumno resuelve, sobre datos server-side:
        - consentimiento_vigente: existe un consentimiento vigente en estado 'otorgado'.
        - biometria_vigente: existe un embedding de referencia vigente.
        puede_rendir = ambos True; razon describe qué falta cuando no.

        Raises:
            ComisionNoEncontradaError: la comisión no existe.
        """
        comision = await self._comision_repo.obtener(comision_id)
        if comision is None:
            raise ComisionNoEncontradaError(f"Comisión {comision_id!r} no existe.")

        usuarios = await self._inscripcion_repo.listar_usuarios_de_comision(comision_id)
        elegibles: list[AlumnoElegibilidad] = []
        for usuario in usuarios:
            consentimiento = await self._consent_repo.vigente(usuario.id)
            consentimiento_vigente = (
                consentimiento is not None and consentimiento.estado == "otorgado"
            )
            embedding = await self._embedding_repo.obtener_vigente(usuario.id)
            biometria_vigente = embedding is not None
            puede_rendir = consentimiento_vigente and biometria_vigente
            elegibles.append(
                AlumnoElegibilidad(
                    usuario_id=usuario.id,
                    username=usuario.username,
                    nombre=usuario.nombre,
                    apellido=usuario.apellido,
                    email=usuario.email,
                    consentimiento_vigente=consentimiento_vigente,
                    biometria_vigente=biometria_vigente,
                    inscripto_en=getattr(usuario, "inscripto_en", None),
                    puede_rendir=puede_rendir,
                    razon=_razon(consentimiento_vigente, biometria_vigente),
                )
            )
        return elegibles
