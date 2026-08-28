"""Sin consentimiento y sin biometría no se rinde, aunque estés inscripto.

Encontrado probando en PRODUCCIÓN (28/8/2026): el gate de perfil vivía solo en
la autoinscripción por código. Un alumno inscripto desde el panel del docente
—que no lo exige— podía crear la sesión, pedir las preguntas, responder y
finalizar. O sea rendir y generar su nota sin haber dado consentimiento y sin
que nadie verificara quién era.

Son dos cosas distintas y las dos importan:

- Sin consentimiento no se puede hacer proctoring: se procesan datos biométricos,
  que la Ley 25.326 trata como sensibles (regla dura #7).
- Sin referencia biométrica no hay contra qué comparar, así que la rendición no
  prueba quién la hizo.

El gate va donde empieza la rendición (crear la sesión CON examen), no en el
onboarding: el consentimiento y la biometría crean sus propias sesiones y no
pueden quedar bloqueados por sí mismos.
"""

from __future__ import annotations

from app.domain.exam_content.perfil_para_rendir import (
    PerfilParaRendir,
    falta_para_rendir,
    puede_rendir,
)


def _completo(**cambios) -> PerfilParaRendir:
    base = {"consintio": True, "tiene_biometria": True, "tiene_foto": True}
    base.update(cambios)
    return PerfilParaRendir(**base)


def test_con_el_perfil_completo_se_rinde():
    assert puede_rendir(_completo()) is True


def test_sin_consentimiento_no():
    assert puede_rendir(_completo(consintio=False)) is False


def test_sin_biometria_no():
    assert puede_rendir(_completo(tiene_biometria=False)) is False


def test_sin_foto_de_referencia_no():
    """Decisión del dueño: la foto es obligatoria, no se puede saltear."""
    assert puede_rendir(_completo(tiene_foto=False)) is False


def test_el_mensaje_dice_QUE_falta():
    """"Perfil incompleto" a secas deja al alumno sin saber qué hacer."""
    assert "consentimiento" in falta_para_rendir(_completo(consintio=False)).lower()
    assert "biométrica" in falta_para_rendir(_completo(tiene_biometria=False)).lower()
    assert "foto" in falta_para_rendir(_completo(tiene_foto=False)).lower()


def test_cuando_falta_todo_lo_dice_junto():
    razon = falta_para_rendir(
        PerfilParaRendir(consintio=False, tiene_biometria=False, tiene_foto=False)
    )
    assert "consentimiento" in razon.lower()
    assert "biométrica" in razon.lower()


def test_con_el_perfil_completo_no_falta_nada():
    assert falta_para_rendir(_completo()) == ""
