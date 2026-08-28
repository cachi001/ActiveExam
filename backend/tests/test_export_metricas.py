"""Las métricas que encabezan un export, como tarjetas y no como una línea suelta.

El resumen se imprimía como texto corrido ("Pueden rendir: 1 de 9"). Funciona,
pero es exactamente el "numerito" que se pierde entre el título y la tabla. El
informe de tutoría que usa la cátedra los muestra como tarjetas: etiqueta chica
en mayúsculas arriba, número grande abajo, y el color diciendo si el número es
bueno o malo. Se lee de un vistazo, que es para lo que existe un resumen.

Este archivo fija QUÉ métricas salen y con qué tono, que es la parte con
decisiones. El dibujo (rectángulos en el PDF, celdas en el Excel) se verifica
generando los archivos en `test_c78_exportables_academicos`.

El tono no es decoración: es lo que hace que el número se entienda sin leer la
etiqueta. Un cero en "faltan ambas" es una buena noticia y un cero en "pueden
rendir" es una catástrofe; pintarlos igual obliga a leer todo.
"""

from __future__ import annotations

from app.application.exam_content.export import (
    resumen_elegibilidad,
    resumen_notas,
)


class _Inscripto:
    def __init__(self, consentimiento: bool, biometria: bool):
        self.consentimiento_vigente = consentimiento
        self.biometria_vigente = biometria


class _Resultado:
    def __init__(self, nota, estado_moodle="pendiente"):
        self.nota = nota
        self.estado_moodle = estado_moodle


# ---------------------------------------------------------------------------
# Inscriptos
# ---------------------------------------------------------------------------


def test_la_primera_metrica_es_cuantos_pueden_rendir():
    # Es el numero por el que se abre el archivo: va primero y no se omite nunca.
    m = resumen_elegibilidad([_Inscripto(True, True)]).metricas()
    assert m[0].valor == "1"
    assert "rendir" in m[0].etiqueta.lower()


def test_pueden_rendir_es_bueno_cuando_estan_todos():
    m = resumen_elegibilidad([_Inscripto(True, True)] * 3).metricas()
    assert m[0].tono == "ok"


def test_pueden_rendir_es_malo_cuando_falta_alguien():
    # Con uno solo que no pueda, el dia del examen hay un problema: el numero
    # tiene que verse como problema, no como un dato mas.
    m = resumen_elegibilidad([_Inscripto(True, True), _Inscripto(False, True)]).metricas()
    assert m[0].tono == "malo"


def test_las_faltas_en_cero_no_generan_tarjeta():
    # Una tarjeta que dice 0 compite por atencion con las que importan.
    m = resumen_elegibilidad([_Inscripto(True, True)]).metricas()
    assert len(m) == 1


def test_cada_motivo_de_falta_tiene_su_tarjeta():
    m = resumen_elegibilidad(
        [
            _Inscripto(True, True),
            _Inscripto(False, True),
            _Inscripto(True, False),
            _Inscripto(False, False),
        ]
    ).metricas()
    etiquetas = " ".join(x.etiqueta.lower() for x in m)
    assert "consentimiento" in etiquetas
    assert "biometr" in etiquetas
    assert len(m) == 4  # pueden rendir + los tres motivos


def test_las_tarjetas_de_falta_van_en_tono_malo():
    m = resumen_elegibilidad([_Inscripto(False, True)]).metricas()
    assert all(x.tono == "malo" for x in m)


def test_el_total_va_en_la_tarjeta_de_pueden_rendir():
    # "1" suelto no dice nada; "1 de 9" es la unica forma de leerlo bien.
    m = resumen_elegibilidad([_Inscripto(True, True)] + [_Inscripto(False, False)] * 8).metricas()
    assert m[0].detalle == "de 9"


# ---------------------------------------------------------------------------
# Notas
# ---------------------------------------------------------------------------


def test_notas_muestra_aprobados_primero():
    m = resumen_notas([_Resultado(90), _Resultado(10)], nota_aprobacion=60).metricas()
    assert "aprob" in m[0].etiqueta.lower()
    assert m[0].valor == "1"


def test_las_notas_sin_cargar_se_ven_como_pendiente():
    m = resumen_notas([_Resultado(90, "pendiente")], nota_aprobacion=60).metricas()
    sin_cargar = [x for x in m if "moodle" in x.etiqueta.lower() or "carg" in x.etiqueta.lower()]
    assert sin_cargar and sin_cargar[0].tono == "malo"


def test_sin_pendientes_no_hay_tarjeta_de_pendiente():
    m = resumen_notas([_Resultado(90, "enviado")], nota_aprobacion=60).metricas()
    assert all("carg" not in x.etiqueta.lower() for x in m)


def test_sin_umbral_no_inventa_una_tarjeta_de_aprobados():
    # Sin nota de aprobacion no se puede decir quien aprobo. Mostrar "Aprobados: 0"
    # seria afirmar que nadie aprobo, que es distinto de no saberlo.
    m = resumen_notas([_Resultado(90)], nota_aprobacion=None).metricas()
    assert all("aprob" not in x.etiqueta.lower() for x in m)
    assert m[0].valor == "1"  # el total, que si se sabe


def test_toda_metrica_tiene_un_tono_conocido():
    todas = (
        resumen_elegibilidad([_Inscripto(False, False)]).metricas()
        + resumen_notas([_Resultado(10, "fallido")], nota_aprobacion=60).metricas()
    )
    assert todas
    assert all(x.tono in {"ok", "malo", "neutro"} for x in todas)
