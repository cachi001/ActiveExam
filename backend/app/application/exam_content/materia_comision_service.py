"""Servicio CRUD de Materias y Comisiones (C-69, D11).

Gestión de materias/comisiones INDEPENDIENTE del import de examen: crear y editar
sin tocar el contenido. Mantiene la capa router→service→repo y reusa tanto la
validación de dominio (entidades ``Materia``/``Comision``) como los errores ya
existentes (duplicado, no-encontrada, validación). No hay DELETE (riesgo de FK con
exámenes/comisiones); el codigo es inmutable (identidad académica de la entidad).
"""

from __future__ import annotations

from app.application.exam_content.codigo_matriculacion import (
    generar_codigo_libre,
    normalizar_codigo,
)
from app.application.exam_content.errors import (
    ComisionNoEncontradaError,
    ComisionNoVaciaError,
    MateriaNoEncontradaError,
    MateriaNoVaciaError,
)
from app.domain.exam_content.entities import Comision, Materia
from app.domain.exam_content.errors import MateriaDuplicadaError


class MateriaComisionService:
    """Casos de uso (admin): CRUD de materias y comisiones, sin reimportar examen."""

    def __init__(self, materia_repo, comision_repo) -> None:
        self._materia_repo = materia_repo
        self._comision_repo = comision_repo

    # -- Materia -----------------------------------------------------------

    async def crear_materia(self, codigo: str, nombre: str) -> Materia:
        """Crea una materia nueva.

        Raises:
            MateriaInvalidaError: codigo/nombre vacíos (validación de dominio).
            MateriaDuplicadaError: ya existe una materia con ese codigo.
        """
        materia = Materia(codigo=codigo, nombre=nombre)  # valida dominio
        return await self._materia_repo.guardar(materia)

    async def actualizar_materia(
        self, materia_id: str, nombre: str, codigo: str | None = None
    ) -> Materia:
        """Actualiza el nombre y (opcionalmente) el codigo de una materia.

        El codigo es EDITABLE: es un atributo único, no la identidad de la fila.
        Si ``codigo`` es None (o vacío tras strip) se preserva el vigente. Un codigo
        que ya pertenece a OTRA materia se rechaza (unicidad).

        Raises:
            MateriaNoEncontradaError: la materia no existe.
            MateriaInvalidaError: nombre/codigo vacíos (validación de dominio).
            MateriaDuplicadaError: el codigo nuevo ya está en uso por otra materia.
        """
        actual = await self._materia_repo.obtener(materia_id)
        if actual is None:
            raise MateriaNoEncontradaError(f"Materia {materia_id!r} no existe.")
        # Código nuevo solo si vino y no es vacío; si no, se preserva el vigente.
        nuevo_codigo = (
            normalizar_codigo(codigo) if codigo and codigo.strip() else actual.codigo
        )
        # Reusa la validación de dominio (codigo y nombre no vacíos).
        Materia(codigo=nuevo_codigo, nombre=nombre)
        # Unicidad: si el codigo cambió, no puede colisionar con OTRA materia.
        if nuevo_codigo != actual.codigo:
            otra = await self._materia_repo.obtener_por_codigo(nuevo_codigo)
            if otra is not None and otra.id != materia_id:
                raise MateriaDuplicadaError(
                    f"Ya existe una materia con codigo {nuevo_codigo!r}."
                )
        actualizada = await self._materia_repo.actualizar(
            materia_id, nombre=nombre, codigo=nuevo_codigo
        )
        assert actualizada is not None  # existía: lo verificamos arriba
        return actualizada

    async def set_activa(self, materia_id: str, activa: bool) -> Materia:
        """Activa o desactiva una materia (C-72 §17). Desactivar = congelar.

        Raises:
            MateriaNoEncontradaError: la materia no existe.
        """
        actual = await self._materia_repo.obtener(materia_id)
        if actual is None:
            raise MateriaNoEncontradaError(f"Materia {materia_id!r} no existe.")
        actualizada = await self._materia_repo.set_activa(materia_id, activa)
        assert actualizada is not None  # existía: lo verificamos arriba
        return actualizada

    async def eliminar_materia(self, materia_id: str) -> None:
        """Elimina una materia SOLO si está 100% vacía (0 inscriptos y 0 exámenes).

        Sus comisiones vacías caen por el FK ON DELETE CASCADE. Si tiene inscriptos
        o exámenes, se bloquea (se ofrece desactivar).

        Raises:
            MateriaNoEncontradaError: la materia no existe.
            MateriaNoVaciaError: tiene inscriptos y/o exámenes.
        """
        actual = await self._materia_repo.obtener(materia_id)
        if actual is None:
            raise MateriaNoEncontradaError(f"Materia {materia_id!r} no existe.")
        inscriptos, examenes = await self._materia_repo.contar_inscriptos_y_examenes(
            materia_id
        )
        if inscriptos > 0 or examenes > 0:
            raise MateriaNoVaciaError(
                f"La materia tiene {inscriptos} inscripto(s) y {examenes} examen(es): "
                "no se puede eliminar. Desactivala en su lugar."
            )
        await self._materia_repo.eliminar(materia_id)

    # -- Comisión ----------------------------------------------------------

    async def crear_comision(
        self,
        materia_id: str,
        codigo: str,
        nombre: str,
        periodo: str | None = None,
        anio: int | None = None,
        codigo_matriculacion: str | None = None,
    ) -> Comision:
        """Crea una comisión dentro de una materia existente (C-70).

        codigo_matriculacion (enrolment key):
        - Si NO se provee → se autogenera ``{materia.codigo}-{sufijo}`` con reintento
          ante colisión de unicidad (23505).
        - Si se provee → se usa EXACTAMENTE (solo strip externo, case-sensitive);
          la unicidad se valida al persistir.

        Raises:
            MateriaNoEncontradaError: la materia no existe.
            ComisionInvalidaError: codigo/nombre vacíos (validación de dominio).
            ComisionDuplicadaError: ya existe (materia_id, codigo).
            CodigoMatriculacionDuplicadoError: el código provisto ya existe.
        """
        materia = await self._materia_repo.obtener(materia_id)
        if materia is None:
            raise MateriaNoEncontradaError(f"Materia {materia_id!r} no existe.")

        async def _persistir(cod_matriculacion: str) -> Comision:
            comision = Comision(
                codigo=codigo,
                nombre=nombre,
                materia_id=materia_id,
                periodo=periodo,
                anio=anio,
                codigo_matriculacion=cod_matriculacion,
            )  # valida dominio
            return await self._comision_repo.guardar(comision)

        if codigo_matriculacion is not None and codigo_matriculacion.strip():
            # Provisto por el docente: tal cual (solo strip externo). Unicidad al persistir.
            return await _persistir(normalizar_codigo(codigo_matriculacion))
        # Autogenerado: reintenta ante colisión de codigo_matriculacion (23505).
        return await generar_codigo_libre(_persistir, materia.codigo)

    async def rotar_codigo_matriculacion(self, comision_id: str) -> Comision:
        """Rota (regenera) el codigo_matriculacion de una comisión (C-70, D5).

        Genera un nuevo código único ``{materia.codigo}-{sufijo}`` (reintento ante
        colisión) y reemplaza el anterior. Las inscripciones existentes quedan
        INTACTAS (rotar no desmatricula a nadie).

        Raises:
            ComisionNoEncontradaError: la comisión no existe.
        """
        comision = await self._comision_repo.obtener(comision_id)
        if comision is None:
            raise ComisionNoEncontradaError(f"Comisión {comision_id!r} no existe.")
        materia = await self._materia_repo.obtener(comision.materia_id)
        if materia is None:  # defensivo: la FK garantiza que existe
            raise ComisionNoEncontradaError(f"Comisión {comision_id!r} no existe.")

        async def _rotar(cod_matriculacion: str) -> Comision:
            actualizada = await self._comision_repo.actualizar_codigo_matriculacion(
                comision_id, cod_matriculacion
            )
            assert actualizada is not None  # existía: lo verificamos arriba
            return actualizada

        return await generar_codigo_libre(_rotar, materia.codigo)

    async def actualizar_comision(
        self,
        comision_id: str,
        nombre: str,
        periodo: str | None = None,
        anio: int | None = None,
        codigo_matriculacion: str | None = None,
    ) -> Comision:
        """Actualiza nombre/periodo/anio de una comisión (codigo y materia inmutables).

        C-70: si se provee ``codigo_matriculacion`` (no vacío), lo fija tal cual
        (solo strip; unicidad al persistir). None → no toca el código vigente.

        Raises:
            ComisionNoEncontradaError: la comisión no existe.
            ComisionInvalidaError: nombre vacío (validación de dominio).
            CodigoMatriculacionDuplicadoError: el código provisto ya pertenece a
                otra comisión.
        """
        actual = await self._comision_repo.obtener(comision_id)
        if actual is None:
            raise ComisionNoEncontradaError(f"Comisión {comision_id!r} no existe.")
        # Reusa la validación de dominio; codigo y materia_id se preservan.
        Comision(
            codigo=actual.codigo,
            nombre=nombre,
            materia_id=actual.materia_id,
            periodo=periodo,
            anio=anio,
        )
        actualizada = await self._comision_repo.actualizar(
            comision_id, nombre=nombre, periodo=periodo, anio=anio
        )
        assert actualizada is not None  # existía: lo verificamos arriba

        if codigo_matriculacion is not None and codigo_matriculacion.strip():
            actualizada = await self._comision_repo.actualizar_codigo_matriculacion(
                comision_id, normalizar_codigo(codigo_matriculacion)
            )
            assert actualizada is not None  # existía: lo verificamos arriba
        return actualizada

    async def set_activa_comision(self, comision_id: str, activa: bool) -> Comision:
        """Activa o desactiva una comisión (baja lógica, C-72 §17).

        Desactivar = congelar SOLO esa comisión: corta inscripciones nuevas por su
        código de matriculación y bloquea iniciar la rendición de sus exámenes. La
        materia y las demás comisiones quedan intactas. Es la alternativa al DELETE
        cuando la comisión no está vacía.

        Raises:
            ComisionNoEncontradaError: la comisión no existe.
        """
        actual = await self._comision_repo.obtener(comision_id)
        if actual is None:
            raise ComisionNoEncontradaError(f"Comisión {comision_id!r} no existe.")
        actualizada = await self._comision_repo.set_activa(comision_id, activa)
        assert actualizada is not None  # existía: lo verificamos arriba
        return actualizada

    async def eliminar_comision(self, comision_id: str) -> None:
        """Elimina una comisión SOLO si está vacía (0 inscriptos y 0 exámenes).

        Raises:
            ComisionNoEncontradaError: la comisión no existe.
            ComisionNoVaciaError: tiene inscriptos y/o exámenes.
        """
        actual = await self._comision_repo.obtener(comision_id)
        if actual is None:
            raise ComisionNoEncontradaError(f"Comisión {comision_id!r} no existe.")
        inscriptos, examenes = await self._comision_repo.contar_inscriptos_y_examenes(
            comision_id
        )
        if inscriptos > 0 or examenes > 0:
            raise ComisionNoVaciaError(
                f"La comisión tiene {inscriptos} inscripto(s) y {examenes} examen(es): "
                "no se puede eliminar."
            )
        await self._comision_repo.eliminar(comision_id)
