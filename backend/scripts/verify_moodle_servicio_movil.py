#!/usr/bin/env python
"""Fase 0 de C-73 — ¿Sirve el SERVICIO MOVIL para devolver la nota con la identidad del docente?

QUE DECIDE ESTE SCRIPT
  Todo el camino nuevo de write-back se apoya en UN supuesto: que el servicio de
  fabrica de Moodle (``moodle_mobile_app``) expone ``mod_assign_save_grade``. Si eso
  es verdad, el docente se autoemite su token (``createmobiletoken`` es default de
  fabrica), escribe la nota con SU identidad y NADIE tiene que tocar la configuracion
  del campus.

  El equipo de Active-IA lo tiene funcionando asi contra ``tup.sied.utn.edu.ar``. Pero
  ese es OTRO campus: que alla ande no prueba que nadie haya tocado la config de este.
  Por eso se verifica antes de escribir una linea del camino nuevo.

  Si el resultado es VERDE -> las fases 1 a 3 son mecanicas.
  Si es ROJO -> hay que volver a discutir habilitar algo en el campus.

NO ESCRIBE NADA (salvo que se lo pidas explicitamente)
  La verificacion de ``mod_assign_save_grade`` usa una SONDA que no califica a nadie:
  se invoca con un ``assignmentid`` invalido y se lee el codigo de error.

    - ``accessexception``  -> la funcion NO esta en el servicio.  ROJO.
    - cualquier otro error -> la funcion SI es alcanzable.        VERDE.

  Esa distincion es todo lo que hace falta: Moodle valida el acceso al servicio ANTES
  de mirar los parametros. Escribir una nota de verdad no aporta nada a esta pregunta.

  El envio real queda detras de ``--escribir`` y exige ``MOODLE_TEST_USERID``.

  ⚠️ CURSO DE PRUEBA, SIEMPRE. Ya se cometio el error de escribir una nota de prueba
  en un curso REAL de produccion. Cualquier corrida con ``--escribir`` va contra un
  curso creado para esto y descartable. Sin excepciones.

USO (PowerShell):
    $env:MOODLE_HOST      = "https://campustest.frm.utn.edu.ar"
    $env:MOODLE_USERNAME  = "profesor_prueba"
    $env:MOODLE_PASSWORD  = "Profesor.2026"
    $env:MOODLE_COURSE_ID = "6"      # curso de PRUEBA, no uno real
    $env:MOODLE_CMID      = "410"    # cmid de la actividad destino
    python scripts/verify_moodle_servicio_movil.py

USO (bash):
    MOODLE_HOST=... MOODLE_USERNAME=... MOODLE_PASSWORD=... \\
    MOODLE_COURSE_ID=6 MOODLE_CMID=410 \\
    python scripts/verify_moodle_servicio_movil.py

OPCIONES:
    --servicio <shortname>  Servicio a probar (default: moodle_mobile_app).
                            Con 'api_moodle' se compara contra el servicio custom.
    --escribir              Ademas de sondear, escribe una nota real (necesita
                            MOODLE_TEST_USERID y MOODLE_TEST_NOTA).

La contrasena se usa SOLO para el canje y no se imprime nunca. El token tampoco.
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

# El script corre desde backend/ y necesita importar app.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOST = (os.environ.get("MOODLE_HOST") or "").rstrip("/")
USERNAME = os.environ.get("MOODLE_USERNAME") or ""
PASSWORD = os.environ.get("MOODLE_PASSWORD") or ""
COURSE_ID = os.environ.get("MOODLE_COURSE_ID") or ""
CMID = os.environ.get("MOODLE_CMID") or ""
TEST_USERID = os.environ.get("MOODLE_TEST_USERID") or ""
TEST_NOTA = os.environ.get("MOODLE_TEST_NOTA") or "1"

ESCRIBIR = "--escribir" in sys.argv


def _servicio_pedido() -> str:
    """Shortname del servicio a probar. Default: el de fabrica."""
    if "--servicio" in sys.argv:
        i = sys.argv.index("--servicio")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return "moodle_mobile_app"


SERVICIO = _servicio_pedido()

# Codigo con el que Moodle contesta cuando la funcion NO esta declarada en el
# servicio externo del token. Es el discriminante de toda la verificacion.
_ERRORCODE_FUERA_DEL_SERVICIO = "accessexception"

# Funciones que el camino nuevo necesita. Se sondean todas: alcanza con que UNA
# falte para que el plan cambie, y es mejor saberlo de una que descubrirlo en la
# fase 2.
_FUNCIONES_REQUERIDAS = (
    # Resolver cmid -> assign.id + leer la config de calificacion del assignment.
    "mod_assign_get_assignments",
    # Escribir la nota con la identidad del docente. LA funcion del cambio.
    "mod_assign_save_grade",
    # Anti-pisado: saber si ya hay nota puesta a mano antes de sobreescribir.
    "mod_assign_get_grades",
    # Resolver alumno -> moodle_userid SIN token institucional (fase 2).
    "core_enrol_get_enrolled_users",
)

_ANCHO = 74


def _seccion(titulo: str) -> None:
    print(f"\n{'-' * _ANCHO}\n{titulo}\n{'-' * _ANCHO}")


def _ok(msg: str) -> None:
    print(f"  [OK]    {msg}")


def _rojo(msg: str) -> None:
    print(f"  [ROJO]  {msg}")


def _aviso(msg: str) -> None:
    print(f"  [AVISO] {msg}")


def _abortar(msg: str) -> None:
    print(f"\nABORTA: {msg}")
    sys.exit(1)


def _validar_entorno() -> None:
    faltan = [
        nombre
        for nombre, valor in (
            ("MOODLE_HOST", HOST),
            ("MOODLE_USERNAME", USERNAME),
            ("MOODLE_PASSWORD", PASSWORD),
        )
        if not valor
    ]
    if faltan:
        _abortar(f"faltan variables de entorno: {', '.join(faltan)}")

    # COURSE_ID y CMID tienen que ser enteros POSITIVOS. El contenedor de dev trae
    # MOODLE_CMID=0 / MOODLE_COURSEID=0 como placeholder, y un "0" pasa cualquier
    # chequeo de "esta vacio?" para despues fallar recien contra Moodle con un error
    # confuso. Se valida el valor, no la presencia.
    for nombre, valor in (("MOODLE_COURSE_ID", COURSE_ID), ("MOODLE_CMID", CMID)):
        if not valor:
            _abortar(f"falta la variable de entorno {nombre}")
        if not valor.isdigit() or int(valor) <= 0:
            _abortar(f"{nombre}={valor!r} no es un id valido (se espera un entero > 0)")

    if ESCRIBIR:
        if not TEST_USERID:
            _abortar("--escribir necesita MOODLE_TEST_USERID (y un curso de PRUEBA)")
        if not TEST_USERID.isdigit() or int(TEST_USERID) <= 0:
            _abortar(f"MOODLE_TEST_USERID={TEST_USERID!r} no es un userid valido")


async def _ws(
    http: httpx.AsyncClient,
    token: str,
    wsfunction: str,
    params: dict[str, str] | None = None,
) -> dict | list:
    """Invoca una funcion de Web Services y devuelve el cuerpo parseado.

    No levanta excepcion ante un error de Moodle: el error ES el dato que se
    quiere leer (el errorcode dice si la funcion esta o no en el servicio).
    """
    data = {
        "wstoken": token,
        "wsfunction": wsfunction,
        "moodlewsrestformat": "json",
        **(params or {}),
    }
    response = await http.post(f"{HOST}/webservice/rest/server.php", data=data)
    if response.status_code >= 400:
        return {"exception": "http", "errorcode": f"http_{response.status_code}"}
    try:
        return response.json()
    except Exception:
        return {"exception": "parse", "errorcode": "respuesta_ilegible"}


def _errorcode(body: dict | list) -> str | None:
    """errorcode de Moodle, o None si la respuesta no es un error."""
    if isinstance(body, dict) and ("exception" in body or "errorcode" in body):
        return str(body.get("errorcode") or "desconocido").lower()
    return None


async def _sondear_funciones(http: httpx.AsyncClient, token: str) -> bool:
    """¿Estan las 4 funciones requeridas dentro del servicio del token?

    Sonda sin efectos: cada funcion se llama con parametros invalidos a proposito.
    Moodle chequea la pertenencia al servicio ANTES de validar parametros, asi que
    un error de parametro ya prueba que la funcion es alcanzable.
    """
    # Parametros deliberadamente invalidos (id 0 no existe en ninguna instalacion).
    sondas: dict[str, dict[str, str]] = {
        "mod_assign_get_assignments": {"courseids[0]": "0"},
        "mod_assign_save_grade": {
            "assignmentid": "0",
            "userid": "0",
            "grade": "0",
            "attemptnumber": "-1",
            "addattempt": "0",
            "workflowstate": "",
            "applytoall": "1",
        },
        "mod_assign_get_grades": {"assignmentids[0]": "0"},
        "core_enrol_get_enrolled_users": {"courseid": "0"},
    }

    todas_ok = True
    for funcion in _FUNCIONES_REQUERIDAS:
        body = await _ws(http, token, funcion, sondas[funcion])
        codigo = _errorcode(body)

        if codigo == _ERRORCODE_FUERA_DEL_SERVICIO:
            _rojo(f"{funcion}: FUERA del servicio '{SERVICIO}' (accessexception)")
            todas_ok = False
        elif codigo is None:
            # Contesto bien incluso con ids invalidos (p.ej. lista vacia): esta.
            _ok(f"{funcion}: alcanzable (respondio sin error)")
        else:
            _ok(f"{funcion}: alcanzable (rechazo el parametro con '{codigo}')")

    return todas_ok


async def _resolver_assignment(
    http: httpx.AsyncClient, token: str
) -> tuple[int | None, str, float | None, int | None]:
    """Traduce cmid -> assign.id y lee la config de calificacion del assignment.

    Es el paso que HOY nos falta: la base guarda ``moodle_cmid`` y
    ``mod_assign_save_grade`` pide el instance id (assign.id). No son lo mismo.

    Devuelve ``(instance_id, tipo, grade_max, scale_id)``. Interpretacion del campo
    ``grade`` (la misma que usa Active-IA, verificada por ellos en su Fase 0):
        grade > 0  -> numerica, grade_max = grade
        grade < 0  -> escala cualitativa, scale_id = abs(grade)
        grade == 0 -> sin calificacion
    """
    body = await _ws(
        http, token, "mod_assign_get_assignments", {"courseids[0]": COURSE_ID}
    )
    codigo = _errorcode(body)
    if codigo:
        _rojo(f"mod_assign_get_assignments fallo: {codigo}")
        return None, "error", None, None

    cmid_buscado = int(CMID)
    for curso in (body or {}).get("courses", []):
        for assignment in curso.get("assignments", []):
            if assignment.get("cmid") != cmid_buscado:
                continue
            instance_id = assignment.get("id")
            grade = assignment.get("grade")
            nombre = assignment.get("name", "(sin nombre)")
            _ok(f"cmid {cmid_buscado} -> assign.id {instance_id}  ({nombre!r})")

            if grade is None or grade == 0:
                _aviso("la actividad NO tiene calificacion configurada (grade=0)")
                return instance_id, "sin_calificacion", None, None
            if grade > 0:
                _ok(f"escala NUMERICA, grade_max = {float(grade):g}")
                return instance_id, "numerica", float(grade), None

            scale_id = abs(int(grade))
            _ok(f"escala CUALITATIVA, scale_id = {scale_id}")
            _aviso(
                "el ORDEN de una escala cualitativa NO es inferible: hay que mapearlo "
                "y verificarlo a mano (el equipo confirmo scale_id=5 con "
                "1=Aprobado 2=Desaprobado, INVERTIDO)"
            )
            return instance_id, "escala", None, scale_id

    _rojo(
        f"el cmid {cmid_buscado} no es una TAREA del curso {COURSE_ID}. "
        "Si es un Cuestionario, este camino no aplica: mod_assign_save_grade solo "
        "sirve para mod_assign."
    )
    return None, "no_encontrado", None, None


async def _verificar_identidad(http: httpx.AsyncClient, token: str) -> None:
    """¿Puede el DOCENTE resolver a sus alumnos sin el token institucional?

    Es la fase 2: si ``core_enrol_get_enrolled_users`` contesta con el token del
    docente, Active Exam deja de necesitar credencial institucional para devolver
    notas, y un docente no puede resolver identidades en cursos donde no da clase.
    """
    body = await _ws(
        http,
        token,
        "core_enrol_get_enrolled_users",
        {"courseid": COURSE_ID},
    )
    codigo = _errorcode(body)
    if codigo:
        _rojo(f"core_enrol_get_enrolled_users fallo: {codigo}")
        return

    usuarios = body if isinstance(body, list) else []
    con_idnumber = sum(1 for u in usuarios if (u.get("idnumber") or "").strip())
    con_email = sum(1 for u in usuarios if (u.get("email") or "").strip())

    _ok(f"{len(usuarios)} usuarios visibles en el curso {COURSE_ID}")
    if not usuarios:
        _aviso("curso sin matriculados: no se puede validar el mapeo de identidad")
        return

    # El mapeo primario es por idnumber (legajo). Sin idnumber hay que caer a email,
    # que es menos confiable como clave institucional.
    _ok(f"con idnumber (legajo): {con_idnumber}/{len(usuarios)}")
    _ok(f"con email: {con_email}/{len(usuarios)}")
    if con_idnumber == 0:
        _aviso(
            "NINGUN usuario expone idnumber. El mapeo por legajo no va a funcionar; "
            "habria que caer a email o pedir que el campus pueble idnumber."
        )


async def _verificar_nota_existente(
    http: httpx.AsyncClient, token: str, instance_id: int
) -> None:
    """Anti-pisado: ¿hay notas ya cargadas en esta actividad?

    Escribir arriba de una nota que un docente puso a mano es destructivo y no se
    puede deshacer desde aca. El camino nuevo tiene que chequear esto antes.
    """
    body = await _ws(
        http, token, "mod_assign_get_grades", {"assignmentids[0]": str(instance_id)}
    )
    codigo = _errorcode(body)
    if codigo:
        _rojo(f"mod_assign_get_grades fallo: {codigo}")
        return

    total = 0
    for assignment in (body or {}).get("assignments", []):
        total += len(assignment.get("grades", []) or [])
    _ok(f"notas ya cargadas en la actividad: {total}")
    if total:
        _aviso(
            "hay notas cargadas: el camino nuevo NO debe sobreescribirlas sin que "
            "alguien lo pida explicitamente"
        )


async def _escribir_nota_real(
    http: httpx.AsyncClient, token: str, instance_id: int
) -> None:
    """Envio real de una nota. Solo con --escribir, y solo en un curso de PRUEBA."""
    print()
    _aviso(f"ESCRIBIENDO nota {TEST_NOTA} al userid {TEST_USERID} — curso {COURSE_ID}")
    _aviso("si este curso no es de prueba, cortá ahora (Ctrl+C)")

    body = await _ws(
        http,
        token,
        "mod_assign_save_grade",
        {
            "assignmentid": str(instance_id),
            "userid": str(TEST_USERID),
            "grade": str(TEST_NOTA),
            "attemptnumber": "-1",  # ultimo intento
            "addattempt": "0",
            "workflowstate": "",
            "applytoall": "1",
            "plugindata[assignfeedbackcomments_editor][text]": (
                "Prueba de verificacion de ActiveExam. Se puede borrar."
            ),
            "plugindata[assignfeedbackcomments_editor][format]": "1",  # HTML
        },
    )
    codigo = _errorcode(body)
    if codigo:
        _rojo(f"la escritura fallo: {codigo}")
        return

    # mod_assign_save_grade devuelve null en exito.
    _ok("nota escrita")
    _aviso(
        "verificá A MANO en la libreta de Moodle que la columna 'Calificador' diga "
        f"el nombre de {USERNAME!r} y no una cuenta de servicio. Eso es el requisito "
        "duro del cambio, y ningun WS lo puede confirmar por vos."
    )


async def main() -> None:
    _validar_entorno()

    print(f"\n{'=' * _ANCHO}")
    print("Fase 0 C-73 — servicio movil para write-back con identidad del docente")
    print(f"{'=' * _ANCHO}")
    print(f"  campus   : {HOST}")
    print(f"  usuario  : {USERNAME}")
    print(f"  servicio : {SERVICIO}")
    print(f"  curso    : {COURSE_ID}   cmid: {CMID}")
    print(f"  escritura: {'SI (--escribir)' if ESCRIBIR else 'no (solo sondas)'}")

    # 1. Canje de contrasena por token — con NUESTRO codigo, no una reimplementacion.
    #    Asi la verificacion prueba el camino que va a correr en produccion.
    _seccion("1. Canje de contrasena por token")
    from app.application.moodle.token_exchange import (
        CredencialesInvalidasError,
        ServicioNoHabilitadoError,
        TokenExchangeError,
        canjear_password_por_token,
    )

    try:
        obtenido = await canjear_password_por_token(
            base_url=HOST,
            username=USERNAME,
            password=PASSWORD,
            service_shortname=SERVICIO,
        )
    except CredencialesInvalidasError as exc:
        _abortar(f"credenciales rechazadas por el campus: {exc}")
    except ServicioNoHabilitadoError as exc:
        _rojo(f"el campus no deja a este usuario emitir token para '{SERVICIO}'")
        _abortar(str(exc))
    except TokenExchangeError as exc:
        _abortar(f"fallo el canje: {exc}")

    token = obtenido.token
    _ok(f"token obtenido para el servicio '{SERVICIO}' (no se imprime)")
    _ok(f"el docente se autoemitio la credencial: nadie toco el campus")

    async with httpx.AsyncClient(timeout=30.0) as http:
        # 2. LA pregunta del script.
        _seccion(f"2. ¿Estan las funciones requeridas en '{SERVICIO}'? (sondas, no escriben)")
        funciones_ok = await _sondear_funciones(http, token)

        # 3. cmid -> instance_id + config de calificacion.
        _seccion("3. Resolucion cmid -> assign.id y escala de la actividad")
        instance_id, tipo, _grade_max, _scale_id = await _resolver_assignment(http, token)

        # 4. Identidad sin token institucional.
        _seccion("4. Mapeo de identidad con el token del DOCENTE (sin institucional)")
        await _verificar_identidad(http, token)

        # 5. Anti-pisado.
        if instance_id:
            _seccion("5. Notas ya cargadas en la actividad (anti-pisado)")
            await _verificar_nota_existente(http, token, instance_id)

        # 6. Escritura real, opcional.
        if ESCRIBIR:
            if not instance_id:
                _rojo("no se puede escribir: no se resolvio el assign.id")
            elif tipo == "sin_calificacion":
                _rojo("no se puede escribir: la actividad no tiene calificacion")
            else:
                _seccion("6. Escritura real de la nota")
                await _escribir_nota_real(http, token, instance_id)

    # Veredicto.
    _seccion("VEREDICTO")
    if funciones_ok and instance_id:
        print("  VERDE — el servicio de fabrica alcanza.")
        print("  El docente escribe la nota con SU identidad y nadie toca el campus.")
        print("  Las fases 1 a 3 del plan son mecanicas.")
        sys.exit(0)

    print("  ROJO — el servicio de fabrica NO alcanza.")
    if not funciones_ok:
        print("  Falta al menos una funcion en el servicio (ver arriba).")
    if not instance_id:
        print(f"  El cmid {CMID} no se resolvio como tarea del curso {COURSE_ID}.")
    print("  Hay que volver a discutir habilitar algo en el campus antes de codear.")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
