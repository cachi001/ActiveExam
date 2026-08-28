"""El registro de auditoría tiene que decir QUIÉN, no un UUID (27/8/2026).

Mirando la pantalla de Auditoría con datos reales, cada inscripción se leía así:

    Inscribió al alumno da108d8a-4986-4271-bf38-dd63b49c2755
    en la comisión df8dc98b-49e3-4144-ac2f-76b12d4f31fb

El registro existe para responder quién hizo qué, y así no responde nada: hay que
salir a buscar dos UUIDs en la base para entender una sola línea. Es el mismo
problema que ya apareció con el username sintético de LTI — una clave interna
mostrada donde va un dato humano.

Importa más que en otras pantallas porque este registro es el que se usa si una
sanción se discute: es la prueba de qué se hizo y cuándo.

El id se conserva como respaldo cuando no hay nombre cargado: es preferible un
UUID a una línea que no identifica a nadie.
"""

from __future__ import annotations

from app.application.audit.etiquetas import etiqueta_alumno, etiqueta_comision


class _Usuario:
    def __init__(self, nombre=None, apellido=None, email=None):
        self.nombre = nombre
        self.apellido = apellido
        self.email = email


class _Comision:
    def __init__(self, codigo=None, nombre=None):
        self.codigo = codigo
        self.nombre = nombre


def test_alumno_con_nombre_completo_y_correo():
    # El CORREO y no el username: es el dato con el que se cruza contra Moodle,
    # y el username puede ser sintetico (los que crea LTI son "lti:1:7").
    u = _Usuario(nombre="Ana", apellido="Lopez", email="ana.lopez@frm.utn.edu.ar")
    assert etiqueta_alumno(u, "id-1") == "Lopez, Ana (ana.lopez@frm.utn.edu.ar)"


def test_alumno_sin_apellido_usa_lo_que_haya():
    u = _Usuario(nombre="Ana", email="ana.lopez@frm.utn.edu.ar")
    assert etiqueta_alumno(u, "id-1") == "Ana (ana.lopez@frm.utn.edu.ar)"


def test_alumno_sin_nombre_cae_al_correo():
    # Un correo identifica y ademas cruza con el campus; un UUID no hace ninguna
    # de las dos cosas.
    u = _Usuario(email="ana.lopez@frm.utn.edu.ar")
    assert etiqueta_alumno(u, "id-1") == "ana.lopez@frm.utn.edu.ar"


def test_alumno_sin_datos_conserva_el_id():
    # Preferible un UUID a una linea que no identifica a nadie.
    assert etiqueta_alumno(None, "id-1") == "id-1"
    assert etiqueta_alumno(_Usuario(), "id-1") == "id-1"


def test_comision_con_codigo_y_nombre():
    c = _Comision(codigo="C1", nombre="Comisión 1")
    assert etiqueta_comision(c, "id-9") == "C1 - Comisión 1"


def test_comision_con_solo_uno_de_los_dos():
    assert etiqueta_comision(_Comision(nombre="Comisión 1"), "id-9") == "Comisión 1"
    assert etiqueta_comision(_Comision(codigo="C1"), "id-9") == "C1"


def test_comision_sin_datos_conserva_el_id():
    assert etiqueta_comision(None, "id-9") == "id-9"


def test_los_espacios_sobrantes_no_ensucian_la_linea():
    u = _Usuario(nombre="  Ana  ", apellido="  Lopez ", email="  ana.lopez@frm.utn.edu.ar ")
    assert etiqueta_alumno(u, "id-1") == "Lopez, Ana (ana.lopez@frm.utn.edu.ar)"
