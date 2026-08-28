"""Contadores de elegibilidad en el export de inscriptos (27/8/2026).

EL PROBLEMA: el listado traía una fila por alumno y nada más. Para saber cuántos
se quedan afuera había que contar a mano, y para saber POR QUÉ, leer fila por
fila. Con 80 inscriptos eso no se hace: se abre el archivo, se ve un muro de
"Sí/No" y se cierra.

Lo que decide si el examen se puede tomar son cuatro números: cuántos pueden
rendir, y de los que no, a cuántos les falta el consentimiento, a cuántos la
biometría y a cuántos las dos cosas. Esa distinción importa porque se resuelven
distinto: el consentimiento lo firma el alumno desde su casa, la captura
biométrica necesita cámara.

Las tres categorías de "no puede" son EXCLUYENTES: quien no tiene ninguna de las
dos cuenta una sola vez, en "faltan ambas". Si se solaparan, la suma daría más
que el total y el número dejaría de servir para decidir.
"""

from __future__ import annotations

from app.application.exam_content.export import resumen_elegibilidad


class _Inscripto:
    """Doble mínimo: el export lee estos atributos con getattr."""

    def __init__(self, consentimiento: bool, biometria: bool):
        self.consentimiento_vigente = consentimiento
        self.biometria_vigente = biometria
        self.puede_rendir = consentimiento and biometria


def test_sin_inscriptos_todo_en_cero():
    r = resumen_elegibilidad([])
    assert r.total == 0
    assert r.pueden_rendir == 0
    assert r.falta_consentimiento == 0
    assert r.falta_biometria == 0
    assert r.faltan_ambas == 0


def test_cuenta_los_que_pueden_rendir():
    r = resumen_elegibilidad([_Inscripto(True, True), _Inscripto(True, True)])
    assert r.total == 2
    assert r.pueden_rendir == 2
    assert r.no_pueden_rendir == 0


def test_separa_el_motivo_de_cada_uno_que_no_puede():
    r = resumen_elegibilidad(
        [
            _Inscripto(True, True),  # listo
            _Inscripto(False, True),  # le falta el consentimiento
            _Inscripto(True, False),  # le falta la biometria
            _Inscripto(False, False),  # le faltan las dos
        ]
    )
    assert r.total == 4
    assert r.pueden_rendir == 1
    assert r.falta_consentimiento == 1
    assert r.falta_biometria == 1
    assert r.faltan_ambas == 1


def test_las_categorias_de_falta_no_se_solapan():
    # Quien no tiene ninguna de las dos cuenta UNA vez, en "faltan ambas". Contarlo
    # en las tres daria una suma mayor que el total y el numero no serviria para
    # decidir si el examen se puede tomar.
    r = resumen_elegibilidad([_Inscripto(False, False)] * 5)
    assert r.faltan_ambas == 5
    assert r.falta_consentimiento == 0
    assert r.falta_biometria == 0
    assert r.falta_consentimiento + r.falta_biometria + r.faltan_ambas == r.no_pueden_rendir


def test_los_que_pueden_mas_los_que_no_dan_el_total():
    inscriptos = [
        _Inscripto(True, True),
        _Inscripto(False, True),
        _Inscripto(True, False),
        _Inscripto(False, False),
        _Inscripto(True, True),
    ]
    r = resumen_elegibilidad(inscriptos)
    assert r.pueden_rendir + r.no_pueden_rendir == r.total == len(inscriptos)


def test_un_dato_ausente_cuenta_como_falta_no_como_listo():
    # Sin dato NO se asume que esta listo: decir que si sin saberlo manda a alguien
    # a rendir que despues no va a poder, y el error aparece el dia del examen.
    class SinDatos:
        pass

    r = resumen_elegibilidad([SinDatos()])
    assert r.pueden_rendir == 0
    assert r.faltan_ambas == 1


def test_lineas_arma_el_texto_que_va_en_el_archivo():
    r = resumen_elegibilidad(
        [_Inscripto(True, True), _Inscripto(False, True), _Inscripto(False, False)]
    )
    texto = " | ".join(r.lineas())
    assert "3" in texto  # el total
    assert "1" in texto
    # Las etiquetas tienen que nombrar QUE falta, no un codigo interno.
    assert "consentimiento" in texto.lower()
    assert "biometr" in texto.lower()


def test_las_lineas_omiten_las_faltas_en_cero():
    # Con todo el curso listo, imprimir "Falta consentimiento: 0" es ruido que
    # compite con el unico numero que importa.
    r = resumen_elegibilidad([_Inscripto(True, True)])
    texto = " ".join(r.lineas()).lower()
    assert "consentimiento" not in texto
    assert "1" in texto
