"""Catalogo VERSIONADO del texto de consentimiento (PURO, C-08, RN-CO-01).

El acuse referencia la VERSION EXACTA del texto mostrado, para sostener la prueba
meses despues (D1). El CONTENIDO legal deriva de C-01 (DPIA + Acuerdo de Nivel de
Proctoring); aqui se modela el versionado y el sellado por hash. Cada version
expone los cinco bloques informativos exigidos (que/como/donde/cuanto/derechos,
US-003 CA-1) en lenguaje claro.

El catalogo es dato de dominio: una version desconocida es invalida (-> 422). El
texto concreto del MVP es un placeholder estructural alineado con C-01; el equipo
legal lo reemplaza por el texto aprobado sin cambiar el contrato (misma version ->
mismo hash; texto nuevo -> nueva version).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConsentText:
    """Una version del texto de consentimiento (cinco bloques, RN-CO-01)."""

    version: str
    que_se_recolecta: str
    como_se_recolecta: str
    donde_se_almacena: str
    cuanto_tiempo: str
    derechos_titular: str

    def cuerpo_canonico(self) -> str:
        """Serializacion deterministica del texto (para hashear el contenido exacto)."""
        return "\n".join(
            [
                f"version={self.version}",
                f"que={self.que_se_recolecta}",
                f"como={self.como_se_recolecta}",
                f"donde={self.donde_se_almacena}",
                f"cuanto={self.cuanto_tiempo}",
                f"derechos={self.derechos_titular}",
            ]
        )

    def hash_texto(self) -> str:
        """SHA-256 del cuerpo canonico: sella el texto exacto de esta version."""
        return hashlib.sha256(self.cuerpo_canonico().encode("utf-8")).hexdigest()

    def bloques(self) -> dict[str, str]:
        """Los cinco bloques informativos (para que la pantalla los muestre)."""
        return {
            "que_se_recolecta": self.que_se_recolecta,
            "como_se_recolecta": self.como_se_recolecta,
            "donde_se_almacena": self.donde_se_almacena,
            "cuanto_tiempo": self.cuanto_tiempo,
            "derechos_titular": self.derechos_titular,
        }


# Version vigente del MVP. CONTENIDO derivado de C-01 (placeholder estructural;
# el texto legal aprobado lo fija el DPIA/Acuerdo). Estructura y versionado fijos.
_V1 = ConsentText(
    version="v1",
    que_se_recolecta=(
        "Una referencia biométrica de tu rostro (un vector numérico derivado de "
        "tu foto, no la foto en sí), imágenes de tu cámara y de tu pantalla "
        "durante el examen, y datos de la sesión: cuándo empezaste, qué "
        "detecciones hubo y desde dónde te conectaste. La referencia biométrica "
        "es un dato sensible y se trata como tal (Ley 25.326)."
    ),
    como_se_recolecta=(
        "Con tu cámara y con capturas de tu pantalla mientras rendís. El primer "
        "análisis ocurre en tu navegador; el servidor lo vuelve a verificar y "
        "sella cada evidencia, así nadie puede alterarla después sin que se note."
    ),
    donde_se_almacena=(
        "En los sistemas de la plataforma, con acceso restringido al personal "
        "autorizado de tu institución: docentes de tu materia y quienes revisan "
        "integridad académica. Tus compañeros no ven nada de esto."
    ),
    cuanto_tiempo=(
        "Mientras la institución los necesite para sostener la evaluación y "
        "resolver cualquier reclamo sobre ella: son la prueba con la que podés "
        "defenderte si se cuestiona tu examen. Si querés que se borren antes, "
        "podés pedirlo (ver tus derechos)."
    ),
    derechos_titular=(
        "Podés pedir acceso a tus datos, su rectificación o su supresión, y "
        "podés impugnar cualquier decisión que te afecte. La decisión "
        "disciplinaria la toma siempre una persona: el sistema marca situaciones "
        "para que alguien las revise, nunca sanciona por su cuenta."
    ),
)

_CATALOGO: dict[str, ConsentText] = {_V1.version: _V1}

VERSION_VIGENTE: str = _V1.version


def get_texto(version: str | None = None) -> ConsentText | None:
    """Devuelve la version pedida (o la vigente si ``None``), o ``None`` si no existe."""
    return _CATALOGO.get(version or VERSION_VIGENTE)


def version_existe(version: str) -> bool:
    """``True`` si la version pertenece al catalogo."""
    return version in _CATALOGO
