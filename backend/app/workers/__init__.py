"""Workers asincronos: re-inferencia, firma de evidencia, reportes, mantenimiento.

Andamio vacio en C-04. Consumen la cola via el puerto de ``messaging`` (cuyo
backend lo decide C-03), por lo que son agnosticos de la pieza concreta.
"""
