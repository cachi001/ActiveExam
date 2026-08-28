"""Qué necesita un alumno para poder rendir.

Existía como chequeo de la MATRICULACIÓN, y solo ahí. Probando en producción
apareció el agujero: al alumno inscripto desde el panel del docente —que no
exige perfil— no lo frenaba nadie, así que creaba la sesión, veía las preguntas,
respondía y finalizaba. Rendía y sacaba nota sin haber dado consentimiento y sin
que nadie hubiera verificado quién era.

Las tres condiciones son del dominio, no de una pantalla:

- **Consentimiento**: sin él no se puede hacer proctoring, porque se procesan
  datos biométricos, que la Ley 25.326 trata como sensibles (regla dura #7).
- **Referencia biométrica**: sin ella no hay contra qué comparar, así que la
  rendición no prueba quién la hizo.
- **Foto de referencia**: decisión del dueño, obligatoria y no salteable desde
  el cliente.

Es una función pura sobre tres booleanos a propósito: quién los resuelve (repos,
caché, lo que sea) no cambia la regla, y así la regla se puede probar sola.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerfilParaRendir:
    """Lo que el alumno tiene resuelto al momento de entrar a rendir."""

    consintio: bool
    tiene_biometria: bool
    tiene_foto: bool


def puede_rendir(perfil: PerfilParaRendir) -> bool:
    """True solo con las tres cosas. Ante cualquier falta, no se rinde."""
    return perfil.consintio and perfil.tiene_biometria and perfil.tiene_foto


def falta_para_rendir(perfil: PerfilParaRendir) -> str:
    """Qué le falta, en una frase para mostrarle al alumno.

    Vacío si no falta nada. Decir "perfil incompleto" a secas lo deja sin saber
    a dónde ir, que es justamente el momento en que menos tiempo tiene.
    """
    faltantes: list[str] = []
    if not perfil.consintio:
        faltantes.append("aceptar el consentimiento")
    if not perfil.tiene_biometria:
        faltantes.append("registrar tu referencia biométrica")
    if not perfil.tiene_foto:
        faltantes.append("sacarte la foto de referencia")

    if not faltantes:
        return ""
    if len(faltantes) == 1:
        return f"Antes de rendir tenés que {faltantes[0]}."
    return f"Antes de rendir tenés que {', '.join(faltantes[:-1])} y {faltantes[-1]}."
