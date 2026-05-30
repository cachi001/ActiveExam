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
        "Se recolectan datos biometricos faciales (un embedding derivado de tu "
        "rostro), senales de tu camara y pantalla durante el examen, y metadatos "
        "de la sesion. El embedding se trata como dato sensible (Ley 25.326)."
    ),
    como_se_recolecta=(
        "Mediante tu camara y la captura de pantalla, con analisis en tu navegador; "
        "el servidor re-procesa y firma la evidencia (cadena de custodia)."
    ),
    donde_se_almacena=(
        "En infraestructura self-hosted de la institucion (soberania de datos), "
        "con la evidencia cifrada at-rest en almacenamiento WORM."
    ),
    cuanto_tiempo=(
        "Segun la politica de retencion del examen; el embedding se elimina al "
        "egreso salvo que un caso disciplinario en curso difiera la eliminacion."
    ),
    derechos_titular=(
        "Tenes derecho de acceso, rectificacion, supresion y a impugnar decisiones; "
        "la decision disciplinaria es siempre humana, el sistema no sanciona solo."
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
