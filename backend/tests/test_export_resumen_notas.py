"""Contadores del export de notas (27/8/2026).

Mismo problema que en el listado de inscriptos: una fila por alumno y ningún
total. Quien baja este archivo lo hace por dos motivos concretos, y ninguno se
respondía sin contar a mano:

1. Cuántos aprobaron. Es el número que se informa.
2. Cuántas notas todavía NO llegaron al campus. Ese es el pendiente de trabajo,
   y es el que se pasa por alto: una nota calculada que quedó sin sincronizar se
   ve igual que una cargada, salvo por una columna al final de la fila.

"Sin nota" se cuenta aparte de "desaprobado". Meter en el mismo bolsón a quien
sacó 3 y a quien no rindió daría un número de desaprobados inflado, y ese número
se informa.
"""

from __future__ import annotations

import pytest

from app.application.exam_content.export import resumen_notas


class _Resultado:
    def __init__(self, nota, estado_moodle="pendiente"):
        self.nota = nota
        self.estado_moodle = estado_moodle


def test_sin_resultados_todo_en_cero():
    r = resumen_notas([], nota_aprobacion=60)
    assert r.total == 0
    assert r.aprobados == 0
    assert r.desaprobados == 0
    assert r.sin_nota == 0
    assert r.sin_cargar == 0


def test_separa_aprobados_de_desaprobados_por_la_nota_de_aprobacion():
    r = resumen_notas(
        [_Resultado(80), _Resultado(60), _Resultado(59), _Resultado(10)],
        nota_aprobacion=60,
    )
    # La nota de aprobación aprueba: 60 con umbral 60 está aprobado.
    assert r.aprobados == 2
    assert r.desaprobados == 2


def test_sin_nota_no_cuenta_como_desaprobado():
    # Quien no rindió no es un desaprobado: sumarlo ahí infla el número que se
    # informa y esconde que falta gente por rendir.
    r = resumen_notas([_Resultado(None), _Resultado(90)], nota_aprobacion=60)
    assert r.sin_nota == 1
    assert r.desaprobados == 0
    assert r.aprobados == 1


def test_las_tres_categorias_dan_el_total():
    resultados = [_Resultado(90), _Resultado(20), _Resultado(None), _Resultado(70)]
    r = resumen_notas(resultados, nota_aprobacion=60)
    assert r.aprobados + r.desaprobados + r.sin_nota == r.total == len(resultados)


def test_cuenta_las_notas_que_no_llegaron_al_campus():
    # 'enviado' y 'manual' ya están en la libreta; el resto es trabajo pendiente.
    r = resumen_notas(
        [
            _Resultado(90, "enviado"),
            _Resultado(80, "manual"),
            _Resultado(70, "pendiente"),
            _Resultado(60, "fallido"),
            _Resultado(50, "sin_token"),
        ],
        nota_aprobacion=60,
    )
    assert r.sin_cargar == 3


def test_una_nota_fallida_cuenta_como_sin_cargar():
    # Un fallo silencioso es exactamente el caso que este contador viene a hacer
    # visible: la nota existe, el alumno la ve, y el campus no la tiene.
    r = resumen_notas([_Resultado(90, "fallido")], nota_aprobacion=60)
    assert r.sin_cargar == 1


@pytest.mark.parametrize("umbral", [None, 0])
def test_sin_umbral_utilizable_no_inventa_aprobados(umbral):
    # Sin nota de aprobación no se puede decir quién aprobó. Se informa el total
    # y las que faltan cargar, que no dependen del umbral.
    r = resumen_notas([_Resultado(90), _Resultado(10)], nota_aprobacion=umbral)
    assert r.total == 2
    assert r.aprobados == 0
    assert r.desaprobados == 0


def test_lineas_nombran_lo_que_cuentan():
    r = resumen_notas(
        [_Resultado(90, "enviado"), _Resultado(10, "pendiente")], nota_aprobacion=60
    )
    texto = " ".join(r.lineas()).lower()
    assert "aprob" in texto
    assert "campus" in texto or "cargar" in texto


def test_no_imprime_el_pendiente_cuando_esta_todo_cargado():
    r = resumen_notas([_Resultado(90, "enviado")], nota_aprobacion=60)
    texto = " ".join(r.lineas()).lower()
    assert "falta" not in texto
