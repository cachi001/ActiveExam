"""El export de inscriptos tiene que decir QUIÉN NO VA A PODER RENDIR.

La pantalla ya lo mostraba por alumno (badges de consentimiento, biometría y un
"No puede rendir" en rojo), pero el archivo que se descarga para trabajar antes
del examen solo llevaba apellido, nombre, usuario, email y fecha de inscripción.
O sea: el dato por el que se abre ese listado quedaba justamente afuera, y había
que ir alumno por alumno en la pantalla para saber a quién avisarle.

Sin consentimiento o sin biometría el alumno NO puede rendir. Es lo que el
docente necesita revisar el día antes, no después.

Tests de función PURA: `filas_inscriptos` no toca la base.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.application.exam_content.export import COLUMNAS_INSCRIPTOS, filas_inscriptos


@dataclass
class _Inscripto:
    """Espeja AlumnoElegibilidadResponse en lo que usa el export."""

    apellido: str
    nombre: str
    username: str
    email: str
    consentimiento_vigente: bool
    biometria_vigente: bool
    puede_rendir: bool
    razon: str | None = None
    inscripto_en: datetime | None = None


def _alumno(**kw) -> _Inscripto:
    base = dict(
        apellido="Perez",
        nombre="Ana",
        username="aperez",
        email="ana@uni.edu",
        consentimiento_vigente=True,
        biometria_vigente=True,
        puede_rendir=True,
        razon=None,
        inscripto_en=datetime(2026, 8, 27, 10, 30, tzinfo=timezone.utc),
    )
    base.update(kw)
    return _Inscripto(**base)


def _columnas() -> list[str]:
    return [c.titulo for c in COLUMNAS_INSCRIPTOS]


def test_las_columnas_incluyen_consentimiento_biometria_y_si_puede_rendir():
    cols = _columnas()
    assert "Consentimiento" in cols
    assert "Biometría" in cols
    assert "¿Puede rendir?" in cols


def test_cada_fila_tiene_tantos_valores_como_columnas():
    """Si se agrega una columna y no su valor, el archivo sale corrido."""
    filas = filas_inscriptos([_alumno()])
    assert len(filas[0]) == len(COLUMNAS_INSCRIPTOS)


def test_alumno_completo_figura_como_que_puede_rendir():
    fila = filas_inscriptos([_alumno()])[0]
    datos = dict(zip(_columnas(), fila))
    assert datos["Consentimiento"] == "Sí"
    assert datos["Biometría"] == "Sí"
    assert datos["¿Puede rendir?"] == "Sí"


def test_sin_biometria_se_ve_que_NO_puede_rendir_y_por_que():
    fila = filas_inscriptos(
        [
            _alumno(
                biometria_vigente=False,
                puede_rendir=False,
                razon="Falta la captura biométrica",
            )
        ]
    )[0]
    datos = dict(zip(_columnas(), fila))
    assert datos["Consentimiento"] == "Sí"
    assert datos["Biometría"] == "No"
    assert datos["¿Puede rendir?"].startswith("NO")
    assert "biométrica" in datos["¿Puede rendir?"]


def test_sin_consentimiento_tampoco_puede_rendir():
    """Triangulación con el otro requisito."""
    fila = filas_inscriptos(
        [
            _alumno(
                consentimiento_vigente=False,
                puede_rendir=False,
                razon="Falta el consentimiento",
            )
        ]
    )[0]
    datos = dict(zip(_columnas(), fila))
    assert datos["Consentimiento"] == "No"
    assert datos["¿Puede rendir?"].startswith("NO")


def test_no_puede_rendir_sin_razon_igual_se_marca():
    """La razón es opcional: sin ella el archivo NO puede decir que sí puede."""
    fila = filas_inscriptos([_alumno(puede_rendir=False, razon=None)])[0]
    datos = dict(zip(_columnas(), fila))
    assert datos["¿Puede rendir?"] == "NO"


def test_las_columnas_de_identificacion_no_se_perdieron():
    """El export sigue sirviendo para cruzar contra el padrón del campus."""
    fila = filas_inscriptos([_alumno()])[0]
    datos = dict(zip(_columnas(), fila))
    assert datos["Apellido"] == "Perez"
    assert datos["Usuario"] == "aperez"
    assert datos["Email"] == "ana@uni.edu"
    assert "2026" in datos["Inscripción"]
