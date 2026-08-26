"""c-78 — La URL del campus sale de la credencial que se está usando.

Encontrado el 26/8/2026 devolviendo notas al campus real. El write-back con la
credencial del DOCENTE (que es el camino principal desde C-73) mandaba el token
del docente pero armaba la URL con la ``base_url`` de la credencial
INSTITUCIONAL. Y esa, en campustest, no está configurada — el propio código lo
dice: "hoy en campustest está muerta".

Resultado: la URL quedaba vacía y el envío moría con

    Request URL is missing an 'http://' or 'https://' protocol

o sea que **el camino principal del write-back no funcionaba nunca** sin una
credencial institucional completa, que es justo la dependencia que ese camino
vino a eliminar.

La regla: el token y la URL viajan juntos. Si se usa el token del docente, se usa
la URL de su credencial; la institucional queda como respaldo.
"""

from __future__ import annotations

import pytest

from app.infrastructure.moodle.transporte import resolver_base_url


def test_usa_la_url_del_docente_cuando_viene():
    url = resolver_base_url(
        base_url_credencial="https://campustest.frm.utn.edu.ar",
        base_url_institucional="",
    )
    assert url == "https://campustest.frm.utn.edu.ar"


def test_cae_a_la_institucional_si_la_credencial_no_trae_url():
    url = resolver_base_url(
        base_url_credencial=None,
        base_url_institucional="https://campus.institucional.edu",
    )
    assert url == "https://campus.institucional.edu"


def test_la_del_docente_gana_sobre_la_institucional():
    """Si el docente conectó su cuenta contra un campus, es ESE el campus donde
    tiene permiso: usar otro le daría un error de credencial confuso."""
    url = resolver_base_url(
        base_url_credencial="https://campustest.frm.utn.edu.ar",
        base_url_institucional="https://otro.campus.edu",
    )
    assert url == "https://campustest.frm.utn.edu.ar"


def test_ignora_una_url_vacia_o_de_espacios():
    url = resolver_base_url(
        base_url_credencial="   ",
        base_url_institucional="https://campus.institucional.edu",
    )
    assert url == "https://campus.institucional.edu"


def test_sin_ninguna_url_falla_con_un_mensaje_que_se_entiende():
    """El error que apareció decía "Request URL is missing an 'http://'", que no
    le dice nada a nadie. Tiene que decir qué falta y quién lo arregla."""
    with pytest.raises(ValueError) as exc:
        resolver_base_url(base_url_credencial=None, base_url_institucional="")

    mensaje = str(exc.value).lower()
    assert "campus" in mensaje
    assert "http" not in mensaje  # no se filtra el error crudo de la librería


def test_limpia_la_barra_final():
    """Sin esto la URL queda con doble barra y Moodle responde 404."""
    url = resolver_base_url(
        base_url_credencial="https://campustest.frm.utn.edu.ar/",
        base_url_institucional="",
    )
    assert url == "https://campustest.frm.utn.edu.ar"
