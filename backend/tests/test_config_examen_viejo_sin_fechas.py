"""Un examen viejo sin fechas no puede quedar imposible de configurar.

Caso real (29/8/2026, el dueño sobre "Segundo parcial — sorteado"): quiso subirle
un intento, apretó Guardar y "no pasaba nada". El examen estaba en un callejón sin
salida de tres capas:

  1. Se creó cuando `apertura`/`cierre` todavía podían ser NULL. Después se volvieron
     obligatorias, y `validar_config_examen` corre sobre la config MERGEADA — así que
     cualquier PATCH, aunque no tocara las fechas, moría en 422 pidiéndolas.
  2. Mandarle las fechas para arreglarlo reventaba en 500: `cambios_bloqueados`
     comparaba `nuevo < vigente["cierre"]` con el vigente en None.
  3. Encima `apertura` es CONGELADO_DURO, así que con un intento finalizado el tutor
     tampoco podía completarla.

Resultado: config congelada para siempre, sin ningún mensaje que lo explicara.

Estos tests son de dominio (funciones puras), sin DB: el bug vive en las reglas, no
en la persistencia.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.exam_content.config import (
    ConfigExamenInvalidaError,
    cambios_bloqueados,
    validar_config_examen,
)

_AHORA = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)


class TestCierreVigenteEnNull:
    """`cambios_bloqueados` no puede explotar cuando el examen no tiene cierre."""

    def test_ponerle_cierre_a_un_examen_sin_cierre_esta_permitido(self) -> None:
        # Antes: TypeError ('<' entre datetime y NoneType) → 500 en la cara del tutor.
        #
        # Y una vez que dejó de explotar, la primera versión lo trataba como "apretar"
        # (de "no cerraba nunca" a "cierra tal día) y lo BLOQUEABA — con lo que el
        # examen seguía siendo imposible de configurar, que era el problema original.
        # La regla correcta: COMPLETAR un dato que nunca se fijó no es modificarlo.
        # Nadie prometió que ese examen no cerraba nunca; era un hueco de datos.
        assert (
            cambios_bloqueados(
                cambios={"cierre": _AHORA},
                vigente={"cierre": None},
                ya_rendido=True,
            )
            == frozenset()
        )

    def test_completar_la_apertura_que_falta_esta_permitido(self) -> None:
        # `apertura` es CONGELADO_DURO, pero eso protege de CAMBIAR cuándo abrió el
        # examen para quien ya rindió. Con la apertura vacía no hay nada que proteger,
        # y bloquearla dejaba al tutor sin poder completar la fecha que el formulario
        # le exige: el examen quedaba trabado para siempre.
        assert (
            cambios_bloqueados(
                cambios={"apertura": _AHORA},
                vigente={"apertura": None},
                ya_rendido=True,
            )
            == frozenset()
        )

    def test_cambiar_una_apertura_ya_fijada_sigue_bloqueado(self) -> None:
        # La protección real no se toca: mover la apertura de un examen que YA la
        # tenía reescribe las reglas para quien rindió con la anterior.
        assert "apertura" in cambios_bloqueados(
            cambios={"apertura": _AHORA + timedelta(days=1)},
            vigente={"apertura": _AHORA},
            ya_rendido=True,
        )

    def test_sin_rendir_ponerle_cierre_esta_permitido(self) -> None:
        assert (
            cambios_bloqueados(
                cambios={"cierre": _AHORA}, vigente={"cierre": None}, ya_rendido=False
            )
            == frozenset()
        )

    def test_intentos_vigente_en_null_no_revienta(self) -> None:
        # Mismo criterio por el otro campo direccional: completar lo que faltaba
        # está permitido, y sobre todo no explota.
        assert (
            cambios_bloqueados(
                cambios={"intentos_permitidos": 2},
                vigente={"intentos_permitidos": None},
                ya_rendido=True,
            )
            == frozenset()
        )

    def test_extender_el_cierre_sigue_permitido(self) -> None:
        # La regla real no se debilita: extender la ventana afloja y sigue permitido.
        assert (
            cambios_bloqueados(
                cambios={"cierre": _AHORA + timedelta(days=7)},
                vigente={"cierre": _AHORA},
                ya_rendido=True,
            )
            == frozenset()
        )

    def test_acortar_el_cierre_sigue_bloqueado(self) -> None:
        assert "cierre" in cambios_bloqueados(
            cambios={"cierre": _AHORA - timedelta(days=1)},
            vigente={"cierre": _AHORA},
            ya_rendido=True,
        )


class TestFechasObligatoriasSoloAlCrear:
    """Exigir fechas a un examen que ya existe sin ellas lo deja inconfigurable."""

    def test_un_examen_nuevo_sigue_necesitando_fechas(self) -> None:
        # La regla NO se cae: al crear, apertura y cierre siguen siendo obligatorias.
        with pytest.raises(ConfigExamenInvalidaError):
            validar_config_examen(
                tiempo_limite_min=60,
                intentos_permitidos=1,
                apertura=None,
                cierre=None,
                nota_maxima=100,
                nota_aprobacion=60,
            )

    def test_un_examen_viejo_sin_fechas_puede_cambiar_otra_cosa(self) -> None:
        # El tutor solo quiere subir los intentos. Exigirle fechas que NO puede
        # completar (apertura es CONGELADO_DURO tras la primera rendición) convierte
        # un examen en curso en un objeto de solo lectura.
        validar_config_examen(
            tiempo_limite_min=60,
            intentos_permitidos=2,
            apertura=None,
            cierre=None,
            nota_maxima=100,
            nota_aprobacion=60,
            examen_preexistente_sin_fechas=True,
        )

    def test_con_fechas_incoherentes_sigue_fallando_aunque_sea_viejo(self) -> None:
        # La tolerancia es SOLO para "no tiene fechas", no para "tiene fechas mal".
        with pytest.raises(ConfigExamenInvalidaError):
            validar_config_examen(
                tiempo_limite_min=60,
                intentos_permitidos=1,
                apertura=_AHORA,
                cierre=_AHORA - timedelta(days=1),
                nota_maxima=100,
                nota_aprobacion=60,
                examen_preexistente_sin_fechas=True,
            )
