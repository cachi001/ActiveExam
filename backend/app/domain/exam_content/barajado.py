"""Barajado determinista de las opciones de una pregunta (PURO).

PROBLEMA QUE RESUELVE: el XML de Moodle lista primero la opcion con
``fraction=100``, asi que al importar, la respuesta correcta queda SIEMPRE en la
posicion 0. Sirviendo las opciones en ese orden, el examen se aprueba marcando
siempre la primera sin leer nada — verificado en vivo: las 20 preguntas del
examen importado tenian la correcta primera, y contestar "la primera" daba 10/10.

POR QUE POR ALUMNO Y NO AL AZAR EN CADA PEDIDO: el orden tiene que ser ESTABLE
para una misma persona. Si cambiara en cada request, al recargar la pagina (o al
reconectar tras un corte) el alumno veria las opciones movidas de lugar, con
respuestas ya marcadas que ahora apuntan a otro texto. La semilla se deriva del
par (alumno, pregunta): distinta para cada alumno — mirar la pantalla del de al
lado no sirve — e identica en todos los pedidos del mismo alumno.

POR QUE ``hashlib`` Y NO ``hash()``: el ``hash()`` de Python esta aleatorizado por
proceso (PYTHONHASHSEED), asi que dos workers de uvicorn le darian al MISMO alumno
ordenes distintos. La semilla debe depender solo de los datos.

Sin framework ni infraestructura (D1): dominio puro, testeable sin DB ni red.
"""

from __future__ import annotations

import hashlib
from random import Random
from typing import TypeVar

T = TypeVar("T")


def semilla_barajado(alumno: str, pregunta_id: str) -> int:
    """Semilla estable para el par (alumno, pregunta). Solo depende de los datos."""
    material = f"{alumno}:{pregunta_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def barajar_opciones(opciones: list[T], *, alumno: str, pregunta_id: str) -> list[T]:
    """Devuelve las ``opciones`` en un orden estable y propio de cada alumno.

    No muta la lista recibida. Preserva TODOS los elementos: barajar no puede
    perder ni duplicar una opcion — con menos opciones de las que el alumno
    respondio, la correccion dejaria de encontrar su respuesta.

    Con 0 o 1 opcion devuelve una copia sin tocar (no hay nada que barajar).
    """
    barajadas = list(opciones)
    if len(barajadas) < 2:
        return barajadas
    Random(semilla_barajado(alumno, pregunta_id)).shuffle(barajadas)
    return barajadas
