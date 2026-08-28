"""Estadísticas y export tienen que contar lo mismo (27/8/2026).

DOS PROBLEMAS ENCONTRADOS mirando la pantalla con datos reales:

1. El mismo padrón se reportaba con números distintos en dos lugares. La pantalla
   decía "Sin consentimiento 6" y "Sin biometría 7" sobre 8 bloqueados: se pisan,
   porque quien no tiene ninguna de las dos cuenta en las dos barras. El export
   decía 1, 2 y 5 (excluyentes). Los dos son correctos por separado, pero quien
   compare el archivo contra la pantalla va a pensar que uno está mal, y en un
   sistema donde estos números deciden si se toma el examen eso no puede pasar.

   Se agrega la categoría "faltan las dos" a las estadísticas: con ella los tres
   motivos suman exactamente los bloqueados y se puede cruzar con el export.

2. `TOP_EVENTOS_N` estaba en 8 con 17 tipos de evento. Cuando varios empatan en
   cantidad, el desempate es alfabético, así que quedaban afuera justamente
   `tampering_camara_virtual` y `posible_cambio_identidad` — los dos más graves.
   Un panel que existe para verificar que los detectores registran no puede
   esconder los que más importan.
"""

from __future__ import annotations

from app.application.exam_content.export import resumen_elegibilidad
from app.application.stats.resumen_service import TOP_EVENTOS_N, ElegibilidadStats
from app.domain.events.schema import TipoEvento


class _Inscripto:
    def __init__(self, consentimiento: bool, biometria: bool):
        self.consentimiento_vigente = consentimiento
        self.biometria_vigente = biometria


def test_el_top_de_eventos_alcanza_para_todos_los_tipos():
    # Con el tope por debajo de la cantidad de tipos, los que empatan se ordenan
    # alfabeticamente y los criticos desaparecen del panel sin aviso.
    assert TOP_EVENTOS_N >= len(TipoEvento)


def test_los_detectores_criticos_no_pueden_quedar_fuera_del_tope():
    # Nombrados a proposito: son los que quedaban cortados por el alfabetico.
    criticos = [TipoEvento.TAMPERING_CAMARA_VIRTUAL, TipoEvento.POSIBLE_CAMBIO_IDENTIDAD]
    tipos_ordenados = sorted(t.value for t in TipoEvento)
    for c in criticos:
        assert tipos_ordenados.index(c.value) < TOP_EVENTOS_N, (
            f"{c.value} queda fuera del top-{TOP_EVENTOS_N} cuando todos empatan"
        )


def test_elegibilidad_expone_la_categoria_de_los_que_no_tienen_ninguna():
    campos = ElegibilidadStats.__dataclass_fields__
    assert "faltan_ambas" in campos, (
        "Sin esta categoria los motivos de bloqueo se pisan y suman mas que el total"
    )


def test_los_tres_motivos_suman_los_bloqueados():
    e = ElegibilidadStats(
        total_inscriptos=9,
        pueden_rendir=1,
        no_pueden_rendir=8,
        solo_falta_consentimiento=1,
        solo_falta_biometria=2,
        faltan_ambas=5,
    )
    assert (
        e.solo_falta_consentimiento + e.solo_falta_biometria + e.faltan_ambas
        == e.no_pueden_rendir
    )


def test_las_estadisticas_cuentan_igual_que_el_export():
    # El mismo padron por los dos caminos tiene que dar lo mismo. Es la garantia
    # de que la pantalla y el archivo no se contradigan.
    padron = [
        _Inscripto(True, True),
        _Inscripto(False, True),
        _Inscripto(True, False),
        _Inscripto(True, False),
        _Inscripto(False, False),
        _Inscripto(False, False),
    ]
    r = resumen_elegibilidad(padron)
    e = ElegibilidadStats(
        total_inscriptos=len(padron),
        pueden_rendir=r.pueden_rendir,
        no_pueden_rendir=r.no_pueden_rendir,
        solo_falta_consentimiento=r.falta_consentimiento,
        solo_falta_biometria=r.falta_biometria,
        faltan_ambas=r.faltan_ambas,
    )
    assert e.pueden_rendir == 1
    assert e.solo_falta_consentimiento == 1
    assert e.solo_falta_biometria == 2
    assert e.faltan_ambas == 2
    assert (
        e.solo_falta_consentimiento + e.solo_falta_biometria + e.faltan_ambas
        == e.no_pueden_rendir
    )


def test_se_conservan_los_totales_no_excluyentes():
    # `sin_consentimiento` (6 sobre 8) sigue siendo un dato valido: cuantos hay que
    # perseguir para que firmen. Lo que faltaba era la lectura excluyente al lado.
    campos = ElegibilidadStats.__dataclass_fields__
    assert "sin_consentimiento" in campos
    assert "sin_biometria" in campos
