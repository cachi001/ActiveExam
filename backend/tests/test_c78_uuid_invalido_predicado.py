"""c-78 — El predicado que reconoce "ese id no es un UUID".

Los dos mensajes de abajo son REALES, copiados de lo que produjo el sistema:

  - el primero es el que apareció en producción (asyncpg rechaza el argumento al
    bindearlo, antes de mandar la query)
  - el segundo es el de Postgres casteando un literal en SQL crudo

El primer intento de arreglo reconocía SOLO el segundo, y el 500 siguió igual.
Por eso hay un test por cada forma: si mañana aparece una tercera, se agrega acá
y se ve enseguida cuál falta.
"""

from __future__ import annotations

from app.infrastructure.persistence.uuid_errors import es_error_de_uuid_invalido

_ASYNCPG_REAL = (
    "(sqlalchemy.dialects.postgresql.asyncpg.Error) <class "
    "'asyncpg.exceptions.DataError'>: invalid input for query argument $1: "
    "'no-es-uuid' (invalid UUID 'no-es-uuid': length must be between 32..36 "
    "characters, got 10)"
)
_POSTGRES_LITERAL = 'invalid input syntax for type uuid: "no-es-uuid"'


def test_reconoce_el_error_de_asyncpg_al_bindear():
    """El que apareció en producción."""
    assert es_error_de_uuid_invalido(RuntimeError(_ASYNCPG_REAL)) is True


def test_reconoce_el_error_de_postgres_al_castear():
    assert es_error_de_uuid_invalido(RuntimeError(_POSTGRES_LITERAL)) is True


def test_lo_reconoce_aunque_este_en_la_causa_encadenada():
    """SQLAlchemy envuelve el error de asyncpg: el texto útil queda abajo."""
    original = RuntimeError(_ASYNCPG_REAL)
    envuelto = RuntimeError("algo generico salio mal")
    envuelto.__cause__ = original

    assert es_error_de_uuid_invalido(envuelto) is True


def test_no_confunde_otros_errores_de_base():
    """Triangulación: si tapara cualquier error de DB, un problema real quedaría
    escondido detrás de un 404 y nadie se enteraría."""
    otros = [
        'duplicate key value violates unique constraint "uq_comision_materia_codigo"',
        'null value in column "titulo" violates not-null constraint',
        "deadlock detected",
        "connection to server was lost",
        'relation "examen_contenido" does not exist',
    ]
    for texto in otros:
        assert es_error_de_uuid_invalido(RuntimeError(texto)) is False, texto


def test_una_cadena_de_causas_larga_no_lo_cuelga():
    """Sin corte, una cadena circular haría un bucle infinito en el handler."""
    a = RuntimeError("a")
    b = RuntimeError("b")
    a.__cause__ = b
    b.__cause__ = a

    assert es_error_de_uuid_invalido(a) is False
