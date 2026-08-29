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
        "Una referencia biométrica de tu rostro: un vector numérico derivado de "
        "tu foto, no la foto en sí. Fotos que toma tu cámara mientras rendís. Y "
        "el registro del examen: cuándo empezaste, cuándo terminaste y las "
        "señales que detecta el sistema, como que la ventana perdió el foco, que "
        "cambiaste de pestaña o que hay más de un rostro frente a la cámara. Tu "
        "pantalla no se graba ni se fotografía en ningún momento."
    ),
    como_se_recolecta=(
        "Con tu cámara, mientras rendís. El primer análisis ocurre en tu "
        "navegador; el servidor lo vuelve a verificar y le calcula a cada foto "
        "una huella digital, así nadie puede alterarla después sin que se note."
    ),
    donde_se_almacena=(
        "En los sistemas de la plataforma, con acceso restringido al personal "
        "autorizado de tu institución: docentes de tu materia y quienes revisan "
        "integridad académica. Tus compañeros no ven nada de esto."
    ),
    cuanto_tiempo=(
        "Las fotos que toma la cámara durante el examen se borran a los 180 "
        "días. De cada una queda el registro de que se tomó y su huella digital, "
        "sin la imagen. Hay una excepción: si tu examen quedó anulado o sigue en "
        "revisión, las fotos se conservan, porque son la prueba en la que se "
        "apoya esa decisión. El registro del examen se conserva junto con tu "
        "nota. La referencia biométrica de tu rostro vale 24 meses: cuando "
        "vence, hacés la captura de nuevo y la nueva reemplaza a la anterior."
    ),
    derechos_titular=(
        "Si tu examen queda anulado, podés abrir tu expediente de pruebas desde "
        "Mis notas: vas a ver la decisión, el motivo, cada señal que detectó el "
        "sistema y las fotos en las que se apoya, con el sello que confirma que "
        "no fueron alteradas. La decisión disciplinaria la toma siempre una "
        "persona: el sistema marca situaciones para que alguien las revise, "
        "nunca sanciona por su cuenta."
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
